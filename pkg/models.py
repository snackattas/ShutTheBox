from pkg import *
from datetime import date
from itertools import combinations
from collections import Counter
from random import choice

class User(ndb.Model):
    """User profile"""
    user_name = ndb.StringProperty(required=True)
    email =ndb.StringProperty()


class Game(ndb.Model):
    """Game-- Game object"""
    number_of_tiles = ndb.IntegerProperty(required=True)
    dice_operation = ndb.StringProperty(required=True)
    game_over = ndb.BooleanProperty(required=True, default=False)
    final_score = ndb.IntegerProperty()
    timestamp = ndb.DateTimeProperty(auto_now_add=True)


class Turn(ndb.Model):
    """Turn-- Specifies a turn of Shut The Box"""
    turn = ndb.IntegerProperty(required=True)
    roll = ndb.IntegerProperty(repeated=True)
    active_tiles = ndb.IntegerProperty(repeated=True)
    game_over = ndb.BooleanProperty(required=True, default=False)
    timestamp = ndb.DateTimeProperty(auto_now=True)

    @classmethod
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


    def invalid_flip(self, tiles_played, active_tiles, roll, dice_operation):
        # First check that only singular tiles were played
        count_unique = Counter(tiles_played).values()
        if sum(count_unique) / float(len(count_unique)) != 1:
            return "The same tile was played twice!"
        # Check that all the tiles played are in the active_tiles array
        for tile in tiles_played:
            if tile not in active_tiles:
                return "The invalid tile {} was played!".format(tile)

        tiles_played_sum = sum(tiles_played)
        if dice_operation == "ADDITION":
            roll_sum = sum(roll)
            if roll_sum != tiles_played_sum:
                return "The sum of the tiles played ({}) is not equal to the "\
                    "sum of the roll {}".format(tiles_played_sum, roll)

        if dice_operation == "MULTIPLICATION":
            roll_product = self.multiply(roll)
            if roll_product != tiles_played_sum:
                return "The sum of the tiles played ({}) is not equal to "\
                    "the product of the roll {}".\
                    format(tiles_played_sum, roll)
        return False

    def multiply(self, tiles):
        return reduce(lambda x, y: x*y, tiles)


class UserRequestForm(messages.Message):
    """User Request Form"""
    user_name = messages.StringField(1, required=True)
    email = messages.StringField(2, required=True)


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
    active_tiles = messages.IntegerField(2, repeated=True)
    dice_operation = messages.StringField(3, required=True)
    message = messages.StringField(4)


class TurnRequestForm(messages.Message):
    urlsafe_key = messages.StringField(1, required=True)
    flip_tiles = messages.IntegerField(2, repeated=True)


class TurnResultForm(messages.Message):
    urlsafe_key = messages.StringField(1, required=True)
    roll = messages.IntegerField(2, repeated=True)
    active_tiles = messages.IntegerField(3, repeated=True)
    valid_move = messages.BooleanField(4, default=False)
    score = messages.IntegerField(5)
    game_over = messages.BooleanField(6, default=False)
    message = messages.StringField(7, required=True)


class NumberOfTiles(messages.Enum):
    """Tiles -- tiles enumeration value"""
    NINE = 9
    TWELVE = 12


class DiceOperation(messages.Enum):
    """DiceRules -- Dice mechanics"""
    ADDITION = 1
    MULTIPLICATION = 2
