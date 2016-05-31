from datetime import date
from protorpc import messages
from google.appengine.ext import ndb
from google.appengine.ext import db

from itertools import combinations
from collections import Counter
from random import choice


class User(ndb.Model):
    """User profile"""
    user_name = ndb.StringProperty(required=True)
    email =ndb.StringProperty()


class Game(ndb.Model):
    """Game-- Game object"""
    total_tiles = ndb.IntegerProperty(required=True, default=9)
    game_over = ndb.BooleanProperty(required=True, default=False)
    final_score = ndb.IntegerProperty()
    timestamp = ndb.DateTimeProperty(auto_now_add=True)


class Turn(ndb.Model):
    """Turn-- Specifies a turn of Shut The Box"""
    turn = ndb.IntegerProperty(required=True)
    roll = ndb.IntegerProperty(repeated=True)
    active_tiles = ndb.IntegerProperty(repeated=True)
    turn_over = ndb.BooleanProperty(required=True, default=False)
    game_over = ndb.BooleanProperty(required=True, default=False)
    timestamp = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def valid_rolls(self, active_tiles, dice_max):
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


    def valid_flip(self, tiles_played, active_tiles, roll):
        # First check that only singular tiles were played
        count_unique = Counter(tiles_played).values()
        if sum(count_unique) / float(len(count_unique)) != 1:
            return "The same tile was played twice!"
        # Check that all the tiles played are in the active_tiles array
        for tile in tiles_played:
            if tile not in active_tiles:
                return "The invalid tile {} was played!".format(tile)
        if sum(roll) != sum(tiles_played):
            return "The tiles played do not equal the roll of {}".format(roll)
        return False

class NewGameForm(messages.Message):
    """NewGameForm-- Inbound form used to create a new game"""
    user_name = messages.StringField(1, required=True)
    total_tiles = messages.IntegerField(2, default=9)


class GameForm(messages.Message):
    """GameForm-- Outbound form for game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    user_name = messages.StringField(2, required=True)
    active_tiles = messages.IntegerField(3, repeated=True)
    game_over = messages.BooleanField(4, required=True)
    message = messages.StringField(5)


class RollForm(messages.Message):
    """RollResultForm-- Inbound form for rolling dice"""
    urlsafe_key = messages.StringField(1, required=True)

class RollResultForm(messages.Message):
    """RollResultForm-- Inbound form for rolling dice"""
    urlsafe_key = messages.StringField(1, required=True)
    roll = messages.IntegerField(2, repeated=True)
    active_tiles = messages.IntegerField(3, repeated=True)
    game_over = messages.BooleanField(4, required=True)
    message = messages.StringField(5, required=True)


class FlipForm(messages.Message):
    """"""
    urlsafe_key = messages.StringField(1, required=True)
    flip_tiles = messages.IntegerField(2, repeated=True)


class FlipResultForm(messages.Message):
    """"""
    urlsafe_key = messages.StringField(1, required=True)
    active_tiles = messages.IntegerField(2, repeated=True)
    valid_move = messages.BooleanField(3, default=False)
    message = messages.StringField(4, required=True)


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)
