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
    user_name = ndb.StringProperty(required=True)
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
        games_played = 0
        cumulative_score = 0
        cumulative_number_of_turns = 0
        for game in games:
            games_played += 1
            cumulative_score += game.final_score
            cumulative_number_of_turns += game.most_recent_turn().turn

        average_score = round(Decimal(
            float(cumulative_score) / games_played), 3)
        average_number_of_turns = round(Decimal(\
            float(cumulative_number_of_turns) / games_played), 3)

        return (games_played, cumulative_score, cumulative_number_of_turns,
               average_score, average_number_of_turns)


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
        if not recent_turn:
            form.turns_played = 0
            return form

        form.turns_played = recent_turn.turn
        form.score = sum(recent_turn.active_tiles)
        return form


class Turn(ndb.Model):
    """Turn-- Specifies a turn of Shut The Box"""
    turn = ndb.IntegerProperty(required=True)
    roll = ndb.IntegerProperty(repeated=True)
    active_tiles = ndb.IntegerProperty(repeated=True)
    turn_over = ndb.BooleanProperty(required=True, default=False)
    game_over = ndb.BooleanProperty(required=True, default=False)
    timestamp = ndb.DateTimeProperty(auto_now_add=True)

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


    def new_turn(self, game, flip_tiles):
        # First end prior turn
        self.turn_over = True
        self.put()

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


    def to_form(self, game_urlsafe_key, valid_move, message):
        form = TurnResultForm()
        form.urlsafe_key = game_urlsafe_key
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
        form.active_tiles = self.active_tiles
        form.turn_over = self.turn_over
        return form

class CreateUserRequestForm(messages.Message):
    """Create User Request Form"""
    user_name = messages.StringField(1, required=True)
    email = messages.StringField(2)

class UserRequestForm(messages.Message):
    user_name = messages.StringField(1, required=True)
    number_of_tiles = messages.EnumField('NumberOfTiles', 2)
    dice_operation = messages.EnumField('DiceOperation', 3)


class AllGamesForm(messages.Message):
    user_name = messages.StringField(1)
    only_open_games = messages.BooleanField(2, default=False)
    only_completed_games = messages.BooleanField(3, default=False)


class UserStatsResultForm(messages.Message):
    games_played = messages.IntegerField(1)
    cumulative_score = messages.IntegerField(2)
    cumulative_number_of_turns = messages.IntegerField(3)
    average_score = messages.FloatField(4)
    average_number_of_turns = messages.FloatField(5)
    message = messages.StringField(6)

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)


class NewGameRequestForm(messages.Message):
    """NewGameForm-- Inbound form used to create a new game"""
    user_name = messages.StringField(1, required=True)
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
    urlsafe_key = messages.StringField(1, required=True)
    flip_tiles = messages.IntegerField(2, repeated=True)


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


class GamesStatusResultForm(messages.Message):
    items = messages.MessageField(GameStatusResultForm, 1, repeated=True)

class PlayByPlayRequestForm(messages.Message):
    urlsafe_key = messages.StringField(1, required=True)


class TurnStatusForm(messages.Message):
    turn = messages.IntegerField(1, required=True)
    roll = messages.IntegerField(2, repeated=True)
    active_tiles = messages.IntegerField(3, repeated=True)
    turn_over = messages.BooleanField(4, required=True)


class TurnsStatusForm(messages.Message):
    items = messages.MessageField(TurnStatusForm, 1, repeated=True)


class LeaderboardRequestForm(messages.Message):
    number_of_tiles = messages.EnumField('NumberOfTiles', 1)
    dice_operation = messages.EnumField('DiceOperation', 2)
    use_cumulative_score = messages.BooleanField(3, default=False)


class LeaderboardResultForm(messages.Message):
    user_name = messages.StringField(1, required=True)
    score = messages.FloatField(2)
    games_played = messages.IntegerField(3)


class LeaderboardsResultForm(messages.Message):
    items = messages.MessageField(LeaderboardResultForm, 1, repeated=True)
    message = messages.StringField(2)

class NumberOfTiles(messages.Enum):
    """Tiles -- tiles enumeration value"""
    NINE = 9
    TWELVE = 12


class DiceOperation(messages.Enum):
    """DiceRules -- Dice mechanics"""
    ADDITION = 1
    MULTIPLICATION = 2
