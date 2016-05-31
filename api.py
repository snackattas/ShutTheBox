import logging
import endpoints
from protorpc import remote, messages

from models import User, Game, Turn
from models import NewGameForm, GameForm, StringMessage
from models import RollForm, RollResultForm
from models import FlipForm, FlipResultForm
from google.appengine.ext import ndb
from utils import get_by_urlsafe, most_recent_roll, create_turn_key, roll_dice

import random
CREATE_USER_REQUEST = endpoints.ResourceContainer(
    user_name=messages.StringField(1),
    email=messages.StringField(2))
NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
ROLL_REQUEST = endpoints.ResourceContainer(RollForm)
FLIP_REQUEST = endpoints.ResourceContainer(FlipForm)

@endpoints.api(name='shut_the_box', version='v1')
class ShutTheBoxApi(remote.Service):
    """Game API"""
    @endpoints.method(request_message=CREATE_USER_REQUEST,
                      response_message=StringMessage,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create a User. Requires a unique email and username"""
        if User.query(User.email == request.email).get():
            raise endpoints.ConflictException(
                'A user with the email {} already exists!'.\
                format(request.email))
        if User.query(User.user_name == request.user_name).get():
            raise endpoints.ConflictException(
                'A user with the name {} already exists!'.\
                format(request.user_name))
        user = User(
            user_name = request.user_name,
            email = request.email)
        user.put()
        return StringMessage(message='User {} created!'.\
                             format(request.user_name))


    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates new game.  Default number of tiles is 9"""
        user = User.query(User.user_name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A user with the name {} does not exist!'.\
                    format(request.user_name))
        game_id = Game.allocate_ids(size=1, parent=user.key)[0]
        game_key = ndb.Key(Game, game_id, parent=user.key)

        game = Game(key = game_key)
        if request.total_tiles:
            game.total_tiles = request.total_tiles
        game.put()
        # Add taskqueue here
        return GameForm(
            urlsafe_key = game.key.urlsafe(),
            user_name = user.user_name,
            active_tiles = range(1, game.total_tiles+1),
            game_over = False,
            message = "Good luck playing Shut The Box, {}!".\
                      format(user.user_name))


    @endpoints.method(request_message=ROLL_REQUEST,
                      response_message=RollResultForm,
                      path='roll',
                      name='roll',
                      http_method='POST')
    def roll(self, request):
        game = get_by_urlsafe(request.urlsafe_key, Game)
        if game.game_over:
            return RollResultForm(
                urlsafe_key=request.urlsafe_key,
                game_over=True,
                message="This game is already over.  Play again by calling new_game()!")

        recent_roll = most_recent_roll(game.key)
        if not recent_roll:
            # If recent_roll is null, this is the first roll/turn.
            active_tiles = range(1, game.total_tiles+1)
            roll = roll_dice(active_tiles)
            turn = Turn(
                key=create_turn_key(game.key),
                turn=1,
                roll=roll,
                active_tiles=active_tiles)
            turn.put()
            return RollResultForm(
                urlsafe_key=request.urlsafe_key,
                roll=roll,
                active_tiles=active_tiles,
                game_over=False,
                message="Call flip() to play your roll")

        if recent_roll.turn_over == False:
            # If latest_roll.turn_over is False, that means roll has already
            # been called, and turn hasn't been called.
            return RollResultForm(
                urlsafe_key=request.urlsafe_key,
                roll=recent_roll.roll,
                active_tiles=recent_roll.active_tiles,
                game_over=False,
                message="You've already rolled!  Now you must play your roll by calling flip()")

        # The following code is reached when roll is called correcly, not on the first turn
        roll = roll_dice(recent_roll.active_tiles)
        logging.warning(roll)
        turn = Turn(
            key=create_turn_key(game.key),
            turn=recent_roll.turn + 1,
            roll=roll,
            active_tiles=recent_roll.active_tiles)

        if sum(roll) not in turn.valid_rolls(recent_roll.active_tiles, 12):
            turn.game_over = True
            turn.put()

            game.game_over = True
            final_score = sum(recent_roll.active_tiles)
            game.final_score = final_score
            game.put()

            return RollResultForm(
                urlsafe_key=request.urlsafe_key,
                roll=roll,
                active_tiles=recent_roll.active_tiles,
                game_over=True,
                message="Game over! Score: {}".format(final_score))

        turn.put()
        return RollResultForm(
            urlsafe_key=request.urlsafe_key,
            roll=roll,
            active_tiles=recent_roll.active_tiles,
            game_over=False,
            message="Roll is valid.  Call flip() to play your roll")


    @endpoints.method(request_message=FLIP_REQUEST,
                      response_message=FlipResultForm,
                      path='turn',
                      name='turn',
                      http_method='POST')
    def flip(self, request):
        game = get_by_urlsafe(request.urlsafe_key, Game)
        if game.game_over:
            return FlipResultForm(
                urlsafe_key=request.urlsafe_key,
                message="This game is already over! Call new_game() to start another game.")

        recent_roll = most_recent_roll(game.key)
        if not recent_roll or recent_roll.turn_over == True:
            return FlipResultForm(
                urlsafe_key=request.urlsafe_key,
                message="You must call roll() before you call flip()")

        error = recent_roll.valid_flip(request.flip_tiles,
                                       recent_roll.active_tiles,
                                       recent_roll.roll)
        if error:
            return FlipResultForm(
                urlsafe_key=request.urlsafe_key,
                active_tiles=recent_roll.active_tiles,
                message=error)

        for roll in request.flip_tiles:
            recent_roll.active_tiles.remove(roll)
        recent_roll.turn_over = True
        recent_roll.put()

        running_score = sum(recent_roll.active_tiles)

        return FlipResultForm(
            urlsafe_key=request.urlsafe_key,
            active_tiles=recent_roll.active_tiles,
            valid_move=True,
            message="Valid move! Running score: {}".format(running_score))


api = endpoints.api_server([ShutTheBoxApi])
