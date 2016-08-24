from pkg import *
from datetime import date
from itertools import combinations
from collections import Counter
from random import randint
import requests
import logging
from settings import MAILGUN_DOMAIN_NAME, MAILGUN_PRIVATE_API_KEY
from settings import MAILGUN_PUBLIC_API_KEY, MAILGUN_SANDBOX_SENDER
from decimal import Decimal

class User(ndb.Model):
    """User profile"""
    username = ndb.StringProperty(required=True)
    email =ndb.StringProperty()

    @classmethod
    def is_email_valid(cls, email):
        request = requests.get(
            "https://api.mailgun.net/v3/address/validate",
            auth=("api", MAILGUN_PUBLIC_API_KEY),
            params={"address": email})
        if request.json().get("is_valid"):
            return True
        return False

class Game(ndb.Model):
    """Game-- Game object"""
    number_of_tiles = ndb.IntegerProperty(required=True)
    dice_operation = ndb.StringProperty(required=True)
    game_over = ndb.BooleanProperty(required=True, default=False)
    final_score = ndb.IntegerProperty()
    timestamp = ndb.DateTimeProperty(auto_now_add=True)

    @classmethod
    def new_game(cls, user_key, number_of_tiles, dice_operation):
        game_id = Game.allocate_ids(size=1, parent=user_key)[0]
        game_key = ndb.Key(Game, game_id, parent=user_key)
        game = Game(
            key=game_key,
            number_of_tiles=number_of_tiles,
            dice_operation=dice_operation)
        game.put()
        return game

    def most_recent_turn(self):
        """Returns the most recent Turn entity that is a child of the parent Game
        entity, or null if no Turn entity Sexists"""
        return Turn.query(ancestor=self.key).order(-Turn.timestamp).get()

    @classmethod
    def games_stats(self, games):
        games_completed = 0
        total_score = 0
        total_turns = 0
        for game in games:
            games_completed += 1
            total_score += game.final_score
            total_turns += game.most_recent_turn().turn

        decimal_places = 3
        average_score = round(Decimal(
            float(total_score) / games_completed), decimal_places)
        average_turns = round(Decimal(
            float(total_turns) / games_completed), decimal_places)

        return (games_completed, total_score, total_turns,
               average_score, average_turns)


    def to_game_result_form(self, message):
        """Returns a GameResultForm representation of the Game"""
        form = GameResultForm()
        form.urlsafe_key = self.key.urlsafe()
        form.number_of_tiles = self.number_of_tiles
        form.dice_operation = self.dice_operation
        form.game_over = self.game_over
        form.message = message
        return form

    def to_game_status_result_form(self):
        form = GameStatusResultForm()
        form.urlsafe_key = self.key.urlsafe()
        form.number_of_tiles = self.number_of_tiles
        form.dice_operation = self.dice_operation
        form.game_over = self.game_over

        recent_turn = self.most_recent_turn()
        # If no turn is logged in the game yet, hardcode a 0
        if not recent_turn:
            form.turns_played = 0
            return form

        form.turns_played = recent_turn.turn
        form.score = sum(recent_turn.active_tiles)
        # TODO: evaluate whether this should be human-readable or not
        form.timestamp = recent_turn.timestamp
        return form

    def to_high_score_form(self):
        """Form used in get_high_scores method"""
        form = GameHighScoresResultForm()
        form.score = self.final_score
        form.username = self.key.parent().get().username
        form.number_of_tiles = self.number_of_tiles
        form.dice_operation = self.dice_operation
        # TODO: make datetime more human readable
        form.timestamp = self.timestamp
        return form

    def format_game_for_email(self, n, number_of_games):
        text = ""
        salutation = """Hello, {0}.  It looks like there are """


class Turn(ndb.Model):
    """Turn-- Specifies a turn of Shut The Box"""
    turn = ndb.IntegerProperty(required=True)
    roll = ndb.IntegerProperty(repeated=True)
    active_tiles = ndb.IntegerProperty(repeated=True)
    turn_over = ndb.BooleanProperty(required=True, default=False)
    game_over = ndb.BooleanProperty(required=True, default=False)
    # auto_now=True sets the property to the current date/time when an entity
    # is created and whenever it's updated
    timestamp = ndb.DateTimeProperty(auto_now=True)

    # Methods for creating turn entities
    @classmethod
    def first_roll(cls, game):
        turn = Turn(
            key=cls.create_turn_key(game.key),
            turn=0,
            active_tiles=range(1, game.number_of_tiles+1))
        turn.roll = turn.roll_dice()
        turn.put()
        return turn


    def end_turn(self):
        self.turn_over = True
        self.put()
        return

    def new_turn(self, game, flip_tiles):
        # Must change the active tiles before calling roll just in case the
        # active tiles change to only being 1-6
        new_turn = Turn(
            key=self.create_turn_key(game.key),
            turn=self.turn + 1,
            active_tiles=self.flip(flip_tiles))
        # Only roll the dice if there are still tiles to flip
        if new_turn.active_tiles:
            new_turn.roll = self.roll_dice()
        new_turn.put()
        return new_turn


    def flip(self, flip_tiles):
        for tile in flip_tiles:
            self.active_tiles.remove(tile)
        return self.active_tiles

    # Utilities for creating turn entities
    @classmethod
    def create_turn_key(cls, game_key):
        turn_id = Turn.allocate_ids(size=1, parent=game_key)[0]
        return ndb.Key(Turn, turn_id, parent=game_key)


    def roll_dice(self):
        # Check if tiles 7 or up are present, return two dice if so
        if filter(lambda n: n>=7, self.active_tiles):
            return [randint(1, 6), randint(1, 6)]
        return [randint(1, 6)]


    def valid_roll_combos(self, active_tiles, dice_max):
        rolls=[]
        active_tiles_count = len(active_tiles)
        if active_tiles_count == 1:
            return active_tiles
        for r in range(1, active_tiles_count+1):
            for combo in combinations(active_tiles, r):
                rolls.append(sum(combo))
        rolls = Counter(rolls).keys()
        rolls.sort()
        return [n for n in rolls if n <= dice_max]


    def invalid_flip(self, flip_tiles, dice_operation):
        """Checks a user's flipped tiles against their active tiles to
        determine if the user's flip is valid or not.

        :param flip_tiles (req): The tiles flipped by the end user.
        :type flip_tiles: list of int
        :param dice_operation (req): ADDITION or MULTIPLICATION.
        :type dice_operation: string
        :return: Returns an error message if the flip was invalid.  Returns
        False if the the flip is valid.
        """
        # First check that only one of each tile was played, no repeats
        count_unique = Counter(flip_tiles).values()
        if sum(count_unique) / float(len(count_unique)) != 1:
            return "The same tile was played twice!"
        # Check that all the tiles played are in the active_tiles array
        for tile in flip_tiles:
            if tile not in self.active_tiles:
                return "The invalid tile {} was played!".format(tile)

        flip_tiles_sum = sum(flip_tiles)
        if dice_operation == "ADDITION":
            roll_sum = sum(self.roll)
            if roll_sum != flip_tiles_sum:
                return "The sum of the tiles played ({}) is not equal to the "\
                    "sum of the roll {}".format(flip_tiles_sum, self.roll)

        if dice_operation == "MULTIPLICATION":
            roll_product = self.multiply(self.roll)
            if roll_product != flip_tiles_sum:
                return "The sum of the tiles played ({}) is not equal to "\
                    "the product of the roll {}".\
                    format(flip_tiles_sum, self.roll)
        return False


    def multiply(self, tiles):
        return reduce(lambda x, y: x*y, tiles)




    def is_game_over(self, game):
        if game.dice_operation == "ADDITION":
            dice_max = 12
            roll_value = sum(self.roll)
        if game.dice_operation == "MULTIPLICATION":
            dice_max = 36
            roll_value = self.multiply(self.roll)

        valid_rolls = self.valid_roll_combos(self.active_tiles, dice_max)
        if roll_value not in valid_rolls:
            return True
        return False


    def end_game(self, game):
        self.game_over = True
        self.turn_over = True
        self.put()

        game.game_over = True
        game.final_score = sum(self.active_tiles)
        game.put()


    # class TurnResultForm(messages.Message):
    #     urlsafe_key = messages.StringField(1, required=True)
    #     roll = messages.IntegerField(2, repeated=True)
    #     active_tiles = messages.IntegerField(3, repeated=True)
    #     valid_move = messages.BooleanField(4, required=True)
    #     score = messages.IntegerField(5)
    #     game_over = messages.BooleanField(6, required=True)
    #     message = messages.StringField(7, required=True)


    def to_form(self, urlsafe_key, valid_move, message):
        form = TurnResultForm()
        form.urlsafe_key = urlsafe_key
        form.roll = self.roll
        form.active_tiles = self.active_tiles
        form.score = sum(self.active_tiles)
        form.valid_move = valid_move
        form.game_over = self.game_over
        form.message = message
        return form


    def to_turn_status_form(self):
        form = TurnStatusForm()
        form.turn = self.turn
        form.roll = self.roll
        # The data in active_tiles passed in here is manipulated by the method
        # main.play_by_play, so that it stores [0] score and [1] tiles_played
        form.score = self.active_tiles[0]
        form.tiles_played = self.active_tiles[1]
        # Report in the last turn if the game is over or not
        if self.game_over == True:
            form.game_over = True
        # If a game is still in session, the last turn_over should be false.
        # Easier to use this as a metric than game_over.
        if self.turn_over == False:
            form.game_over = False
        return form

class CreateUserRequestForm(messages.Message):
    """Create User Request Form"""
    username = messages.StringField(1, required=True)
    email = messages.StringField(2)

class UserRequestForm(messages.Message):
    username = messages.StringField(1, required=True)
    number_of_tiles = messages.EnumField('NumberOfTiles', 2)
    dice_operation = messages.EnumField('DiceOperation', 3)


class GamesRequestForm(messages.Message):
    username = messages.StringField(1)
    games_in_progress = messages.BooleanField(2, default=False)
    finished_games = messages.BooleanField(3, default=False)


class UserStatsResultForm(messages.Message):
    games_completed = messages.IntegerField(1)
    total_score = messages.IntegerField(2)
    total_turns = messages.IntegerField(3)
    average_score = messages.FloatField(4)
    average_turns = messages.FloatField(5)
    message = messages.StringField(6)

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)


class NewGameRequestForm(messages.Message):
    """NewGameForm-- Inbound form used to create a new game"""
    username = messages.StringField(1, required=True)
    number_of_tiles = messages.EnumField('NumberOfTiles', 2)
    dice_operation = messages.EnumField('DiceOperation', 3)


class GameResultForm(messages.Message):
    """GameForm-- Outbound form for game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    number_of_tiles = messages.IntegerField(2, required=True)
    dice_operation = messages.StringField(3, required=True)
    game_over = messages.BooleanField(4, required=True)
    message = messages.StringField(5)


class TurnRequestForm(messages.Message):
    flip_tiles = messages.IntegerField(1, repeated=True)


class TurnResultForm(messages.Message):
    urlsafe_key = messages.StringField(1, required=True)
    roll = messages.IntegerField(2, repeated=True)
    active_tiles = messages.IntegerField(3, repeated=True)
    valid_move = messages.BooleanField(4, required=True)
    score = messages.IntegerField(5)
    game_over = messages.BooleanField(6, required=True)
    message = messages.StringField(7, required=True)


class GameStatusResultForm(messages.Message):
    urlsafe_key = messages.StringField(1, required=True)
    number_of_tiles = messages.IntegerField(2)
    dice_operation = messages.StringField(3)
    turns_played = messages.IntegerField(4)
    score = messages.IntegerField(5)
    game_over = messages.BooleanField(6)
    timestamp = message_types.DateTimeField(7)


class GamesStatusResultForm(messages.Message):
    games = messages.MessageField(GameStatusResultForm, 1, repeated=True)


class URLSafeKeyRequestForm(messages.Message):
    urlsafe_key = messages.StringField(1, required=True)

class CancelResultForm(messages.Message):
    cancelled = messages.BooleanField(1, required=True)
    error = messages.StringField(2)

class TurnStatusForm(messages.Message):
    turn = messages.IntegerField(1, required=True)
    roll = messages.IntegerField(2, repeated=True)
    tiles_played = messages.IntegerField(3, repeated=True)
    score = messages.IntegerField(4, required=True)
    game_over = messages.BooleanField(5)


class TurnsStatusForm(messages.Message):
    turns = messages.MessageField(TurnStatusForm, 1, repeated=True)


# Section for get_high_scores method
class HighScoresRequestForm(messages.Message):
    number_of_tiles = messages.EnumField('NumberOfTiles', 1)
    dice_operation = messages.EnumField('DiceOperation', 2)
    number_of_results = messages.IntegerField(3, default=20)


class GameHighScoresResultForm(messages.Message):
    score = messages.IntegerField(1)
    username = messages.StringField(2)
    number_of_tiles = messages.IntegerField(3)
    dice_operation = messages.StringField(4)
    timestamp = message_types.DateTimeField(5)


class TotalHighScoresResultForm(messages.Message):
    high_scores = messages.MessageField(GameHighScoresResultForm, 1,
        repeated=True)
    message = messages.StringField(2)


# Section for get_user_rankings method
class LeaderboardRequestForm(messages.Message):
    number_of_tiles = messages.EnumField('NumberOfTiles', 1)
    dice_operation = messages.EnumField('DiceOperation', 2)


class UserLeaderboardResultForm(messages.Message):
    username = messages.StringField(1, required=True)
    average_score = messages.FloatField(2)
    average_turns = messages.FloatField(3)
    total_score = messages.IntegerField(4)
    games_completed = messages.IntegerField(5)
    rank = messages.IntegerField(6)


class TotalLeaderboardResultForm(messages.Message):
    ranked_users = messages.MessageField(UserLeaderboardResultForm, 1,
        repeated=True)
    message = messages.StringField(2)


class NumberOfTiles(messages.Enum):
    """Tiles -- tiles enumeration value"""
    NINE = 9
    TWELVE = 12


class DiceOperation(messages.Enum):
    """DiceRules -- Dice mechanics"""
    ADDITION = 1
    MULTIPLICATION = 2
