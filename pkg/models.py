"""models.py - This file contains the class definitions for the Datastore
entities used by ShutTheBox.  In addition, these Datastore entities also
function as python classes, and as a result contain methods that contain
game logic and methods that send data to Cloud Endpoint result forms.  The
request and result form classes are also stored here."""

from protorpc import messages, message_types
from google.appengine.ext import ndb
from google.appengine.api import memcache

from itertools import combinations
from collections import Counter
from decimal import Decimal
from random import randint

from settings import MAILGUN_PUBLIC_API_KEY
import requests
import pickle
import logging


class User(ndb.Model):
    """User object"""
    username = ndb.StringProperty(required=True)
    email = ndb.StringProperty()
    email_notification = ndb.BooleanProperty()

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
    """Game object"""
    number_of_tiles = ndb.IntegerProperty(required=True)
    dice_operation = ndb.StringProperty(required=True)
    game_over = ndb.BooleanProperty(required=True, default=False)
    final_score = ndb.IntegerProperty()
    timestamp = ndb.DateTimeProperty(auto_now_add=True)

    # Method for creating game entities
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

    # Method for helping create turn entities
    def most_recent_turn(self):
        """Returns the most recent Turn entity that is a child of the parent Game
        entity, or null if no Turn entity exists"""
        MEMCACHE_KEY = self.key.urlsafe()
        most_recent_turn = memcache.get(MEMCACHE_KEY)
        if most_recent_turn is not None:
            return pickle.loads(most_recent_turn)
        most_recent_turn = Turn.query(ancestor=self.key).\
            order(-Turn.timestamp).get()
        if most_recent_turn is not None:
            if not memcache.replace(key=MEMCACHE_KEY,
                value=pickle.dumps(most_recent_turn), time=360):
                if not memcache.add(key=MEMCACHE_KEY,
                    value=pickle.dumps(most_recent_turn), time=360):
                    logging.warning("Memcache set failed!")
        return most_recent_turn

    # Method for creating statistics about games
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

    # Methods for creating forms
    def to_new_game_result_form(self, message):
        # Form used in new_game method
        form = NewGameResultForm()
        form.urlsafe_key = self.key.urlsafe()
        form.number_of_tiles = self.number_of_tiles
        form.dice_operation = self.dice_operation
        form.game_over = self.game_over
        form.message = message
        return form

    def to_find_games_result_form(self):
        # Form used in find_games method
        form = FindGamesResultForm()
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
        form.timestamp = recent_turn.timestamp
        return form

    def to_high_scores_result_form(self):
        # Form used in get_high_scores method
        form = HighScoresResultForm()
        form.score = self.final_score
        form.username = self.key.parent().get().username
        form.number_of_tiles = self.number_of_tiles
        form.dice_operation = self.dice_operation
        form.timestamp = self.timestamp
        return form


class Turn(ndb.Model):
    """Turn object"""
    turn = ndb.IntegerProperty(required=True)
    roll = ndb.IntegerProperty(repeated=True)
    active_tiles = ndb.IntegerProperty(repeated=True)
    turn_over = ndb.BooleanProperty(required=True, default=False)
    game_over = ndb.BooleanProperty(required=True, default=False)
    # timestamp refreshes when entity is updated
    timestamp = ndb.DateTimeProperty(auto_now=True)

    # Methods for creating turn entities
    @classmethod
    def first_turn(cls, game):
        turn = Turn(
            key=cls.create_turn_key(game.key),
            turn=0,
            active_tiles=range(1, game.number_of_tiles+1))
        turn.roll = turn.roll_dice()
        turn.put()
        return turn

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

    def end_turn(self):
        self.turn_over = True
        self.put()
        return

    # Methods for helping create turn entities
    @classmethod
    def create_turn_key(cls, game_key):
        turn_id = Turn.allocate_ids(size=1, parent=game_key)[0]
        return ndb.Key(Turn, turn_id, parent=game_key)

    def flip(self, flip_tiles):
        for tile in flip_tiles:
            self.active_tiles.remove(tile)
        return self.active_tiles

    def roll_dice(self):
        # Check if tiles 7 or up are present, return two dice if so
        if filter(lambda n: n>=7, self.active_tiles):
            return [randint(1, 6), randint(1, 6)]
        return [randint(1, 6)]

    def valid_tile_combos(self, active_tiles, dice_operation):
        # Calculates a list of valid tile combos based on the active tiles left
        # Ex:
        # valid_tile_combos([1,2,3,4,5,6,7], "ADDITION")
        #    [1,2,3,4,5,6,7,8,9,10,11,12]
        #
        # valid_tile_combos([1,2,5,6], "ADDITION")
        #    [1,2,5,6,7,8,9,11,12]
        #
        # valid_tile_combos([1,2,11,12], "MULTIPLICATION")
        #    [1,2,11,12,13,14,15,23,24,25,26]

        # if there's only one active tile left, it's the only valid tile combo
        active_tiles_count = len(active_tiles)
        if active_tiles_count == 1:
            return active_tiles

        if dice_operation == "ADDITION":
            dice_max = 12
        if dice_operation == "MULTIPLICATION":
            dice_max = 36

        # The rolls array is basically an array of all the sums of unique
        # combinations of tiles in the active_tiles array.  Unique
        # combinations of tiles can yield the same sum though, like [3,
        # 4] and [5,2]; the rolls array does not discriminate for unique sums
        rolls = []
        for r in range(1, active_tiles_count+1):
            for combo in combinations(active_tiles, r):
                rolls.append(sum(combo))

        # Calling Counter in this way returns only the unique sums in the
        # rolls array
        rolls = Counter(rolls).keys()
        rolls.sort()
        return [n for n in rolls if n <= dice_max]

    def invalid_flip(self, flip_tiles, dice_operation):
        # Checks a user's flipped tiles against their active tiles to determine
        # if the user's flip is valid or not.

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
        # First determine how to compute the dice roll
        if game.dice_operation == "ADDITION":
            roll_value = sum(self.roll)
        if game.dice_operation == "MULTIPLICATION":
            roll_value = self.multiply(self.roll)

        # Then see if the row value is among the possible sums of active_tile
        # combinations
        valid_rolls = self.valid_tile_combos(self.active_tiles,
                                             game.dice_operation)
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

    # Methods for creating forms
    def to_turn_result_form(self, urlsafe_key, valid_move, message):
        form = TurnResultForm()
        form.urlsafe_key = urlsafe_key
        form.roll = self.roll
        form.active_tiles = self.active_tiles
        form.score = sum(self.active_tiles)
        form.valid_move = valid_move
        form.game_over = self.game_over
        form.message = message
        return form

    def to_turn_report_result_form(self):
        form = TurnReportResultForm()
        form.turn = self.turn
        form.roll = self.roll
        # The data in active_tiles passed in here is manipulated by the method
        # main.get_game_history, so that it stores [0] score and [1] tiles_played
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
    """CreateUserRequestForm-- Inbound form used to create a new user"""
    username = messages.StringField(1, required=True)
    email = messages.StringField(2)
    email_notification = messages.BooleanField(3, default=True)
class CreateUserResultForm(messages.Message):
    """CreateUserResultForm-- Outbound form returning new user information"""
    message = messages.StringField(1, required=True)


class EmailNotificationRequestForm(messages.Message):
    """EmailNotificationRequestForm-- Inbound form to set email notification
    preferences"""
    username = messages.StringField(1, required=True)
    email_notification = messages.BooleanField(2, required=True)
class EmailNotificationResulForm(messages.Message):
    """EmailNotificationResulForm-- Outbound form for changing email
    notification preferences"""
    message = messages.StringField(1, required=True)


class NewGameRequestForm(messages.Message):
    """NewGameForm-- Inbound form used to create a new game"""
    username = messages.StringField(1, required=True)
    number_of_tiles = messages.EnumField('NumberOfTiles', 2)
    dice_operation = messages.EnumField('DiceOperation', 3)
class NewGameResultForm(messages.Message):
    """NewGameResultForm-- Outbound form returning information about new game"""
    urlsafe_key = messages.StringField(1, required=True)
    number_of_tiles = messages.IntegerField(2, required=True)
    dice_operation = messages.StringField(3, required=True)
    game_over = messages.BooleanField(4, required=True)
    message = messages.StringField(5)


class TurnRequestForm(messages.Message):
    """TurnRequestForm-- Inbound form used to play a turn"""
    flip_tiles = messages.IntegerField(1, repeated=True)
class TurnResultForm(messages.Message):
    """TurnResultForm-- Outbound form for playing a turn"""
    urlsafe_key = messages.StringField(1, required=True)
    roll = messages.IntegerField(2, repeated=True)
    active_tiles = messages.IntegerField(3, repeated=True)
    valid_move = messages.BooleanField(4, required=True)
    score = messages.IntegerField(5)
    game_over = messages.BooleanField(6, required=True)
    message = messages.StringField(7, required=True)


class CancelResultForm(messages.Message):
    """CancelResultForm-- Outbound form for cancelling a game"""
    cancelled = messages.BooleanField(1, required=True)
    error = messages.StringField(2)


class FindGamesRequestForm(messages.Message):
    """FindGamesRequestForm-- Inbound form for searching for games"""
    username = messages.StringField(1)
    games_in_progress = messages.BooleanField(2, default=False)
    finished_games = messages.BooleanField(3, default=False)
    number_of_tiles = messages.EnumField('NumberOfTiles', 4)
    dice_operation = messages.EnumField('DiceOperation', 5)
class FindGamesResultForm(messages.Message):
    """FindGamesResultForm-- Intermediate form for an individual game's basic
    information"""
    urlsafe_key = messages.StringField(1, required=True)
    number_of_tiles = messages.IntegerField(2)
    dice_operation = messages.StringField(3)
    turns_played = messages.IntegerField(4)
    score = messages.IntegerField(5)
    game_over = messages.BooleanField(6)
    timestamp = message_types.DateTimeField(7)
class TotalFindGamesResultForm(messages.Message):
    """TotalFindGamesResultForm-- Aggregate of FindGamesResultForm; putbound
    form for the results from the query in FindGamesRequestForm"""
    games = messages.MessageField(FindGamesResultForm, 1, repeated=True)


class UserStatsRequestForm(messages.Message):
    """UserStatsRequestForm-- Inbound form for requesting stats about a
    particular user; uses filters"""
    username = messages.StringField(1, required=True)
    number_of_tiles = messages.EnumField('NumberOfTiles', 2)
    dice_operation = messages.EnumField('DiceOperation', 3)
class UserStatsResultForm(messages.Message):
    """UserStatsResultForm-- Outbound form for stats about a particular user"""
    games_completed = messages.IntegerField(1)
    total_score = messages.IntegerField(2)
    total_turns = messages.IntegerField(3)
    average_score = messages.FloatField(4)
    average_turns = messages.FloatField(5)
    message = messages.StringField(6)


class HighScoresRequestForm(messages.Message):
    """HighScoresRequestForm-- Inbound form for getting high scores"""
    number_of_tiles = messages.EnumField('NumberOfTiles', 1)
    dice_operation = messages.EnumField('DiceOperation', 2)
    number_of_results = messages.IntegerField(3, default=20)
class HighScoresResultForm(messages.Message):
    """HighScoresResultForm-- Intermediate form for an idividual game's score"""
    score = messages.IntegerField(1)
    username = messages.StringField(2)
    number_of_tiles = messages.IntegerField(3)
    dice_operation = messages.StringField(4)
    timestamp = message_types.DateTimeField(5)
class TotalHighScoresResultForm(messages.Message):
    """TotalHighScoreResultForm-- Aggregate of HighScoresResultForm; outbound
    form containing the high scores in order from lowest to highest"""
    high_scores = messages.MessageField(HighScoresResultForm, 1,
        repeated=True)
    message = messages.StringField(2)


class LeaderboardRequestForm(messages.Message):
    """LeaderboardRequestForm-- Inbound form retrieving the leaderboard"""
    number_of_tiles = messages.EnumField('NumberOfTiles', 1)
    dice_operation = messages.EnumField('DiceOperation', 2)
    username = messages.StringField(3)
class UserLeaderboardResultForm(messages.Message):
    """UserLeaderboardResultForm-- Intermediate form for an individual user's
    rank in the leaderboard"""
    username = messages.StringField(1, required=True)
    average_score = messages.FloatField(2)
    average_turns = messages.FloatField(3)
    total_score = messages.IntegerField(4)
    games_completed = messages.IntegerField(5)
    rank = messages.IntegerField(6)
class TotalLeaderboardResultForm(messages.Message):
    """TotalLeaderboardResultForm-- Aggregate of UserLeaderboardResultForm;
    outbound form containing the leaderboard, from lowest to highest rank"""
    ranked_users = messages.MessageField(UserLeaderboardResultForm, 1,
        repeated=True)
    message = messages.StringField(2)


class TurnReportResultForm(messages.Message):
    """TurnReportResultForm-- Intermediate form for an individual turn in a
    game"""
    turn = messages.IntegerField(1, required=True)
    roll = messages.IntegerField(2, repeated=True)
    tiles_played = messages.IntegerField(3, repeated=True)
    score = messages.IntegerField(4, required=True)
    game_over = messages.BooleanField(5)
class AllTurnsReportResultForm(messages.Message):
    """AllTurnsReportResultForm-- Aggregate of TurnReportResultForm; outbound
    form containing all turns played in a particular game"""
    turns = messages.MessageField(TurnReportResultForm, 1, repeated=True)


class NumberOfTiles(messages.Enum):
    """NumberOfTiles-- tiles enumeration value"""
    NINE = 9
    TWELVE = 12


class DiceOperation(messages.Enum):
    """DiceOperation-- Dice enumeration values"""
    ADDITION = 1
    MULTIPLICATION = 2

# Uncomment out these methods if using test_method
class InsertOrDeleteDataRequestForm(messages.Message):
    delete_everything = messages.BooleanField(1, default=False)
class InsertOrDeleteDataResultForm(messages.Message):
    message = messages.StringField(1)
