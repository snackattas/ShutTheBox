from pkg import *
from datetime import date
from itertools import combinations
from collections import Counter
from random import randint
import requests
import logging
from settings import MAILGUN_DOMAIN_NAME, MAILGUN_PRIVATE_API_KEY
from settings import MAILGUN_PUBLIC_API_KEY, MAILGUN_SANDBOX_SENDER

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
        return Turn.query(ancestor=self.key).order(-Turn.timestamp).get()

    def to_form(self, message):
        """Returns a GameResultForm representation of the Game"""
        form = GameResultForm()
        form.urlsafe_key = self.key.urlsafe()
        form.number_of_tiles = self.number_of_tiles
        form.dice_operation = self.dice_operation
        form.game_over = self.game_over
        form.message = message
        return form


class Turn(ndb.Model):
    """Turn-- Specifies a turn of Shut The Box"""
    turn = ndb.IntegerProperty(required=True)
    roll = ndb.IntegerProperty(repeated=True)
    active_tiles = ndb.IntegerProperty(repeated=True)
    game_over = ndb.BooleanProperty(required=True, default=False)
    timestamp = ndb.DateTimeProperty(auto_now_add=True)

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
        # First check that only singular tiles were played
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


    def roll_dice(self):
        if filter(lambda n: n>=6, self.active_tiles):
            return [randint(1, 6), randint(1, 6)]
        return [randint(1, 6)]

    @classmethod
    def create_turn_key(cls, game_key):
        turn_id = Turn.allocate_ids(size=1, parent=game_key)[0]
        return ndb.Key(Turn, turn_id, parent=game_key)

    @classmethod
    def first_roll(cls, game):
        turn = Turn(
            key=cls.create_turn_key(game.key),
            turn=1,
            active_tiles=range(1, game.number_of_tiles+1))
        turn.roll = turn.roll_dice()
        turn.put()
        return turn

    def new_roll(self, game):
        logging.warning(self.turn)
        new_roll = Turn(
            key=self.create_turn_key(game.key),
            turn=self.turn + 1,
            roll=self.roll_dice(),
            active_tiles=self.active_tiles)
        new_roll.put()
        return new_roll


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
        self.put()

        game.game_over = True
        game.final_score = sum(self.active_tiles)
        game.put()


    def flip(self, flip_tiles):
        for tile in flip_tiles:
            self.active_tiles.remove(tile)
        self.put()
        return self.active_tiles


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
    number_of_tiles = messages.IntegerField(2, required=True)
    dice_operation = messages.StringField(3, required=True)
    game_over = messages.BooleanField(4, required=True)
    message = messages.StringField(5, required=True)


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


class NumberOfTiles(messages.Enum):
    """Tiles -- tiles enumeration value"""
    NINE = 9
    TWELVE = 12


class DiceOperation(messages.Enum):
    """DiceRules -- Dice mechanics"""
    ADDITION = 1
    MULTIPLICATION = 2
