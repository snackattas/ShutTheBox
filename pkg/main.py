import logging
from pkg import *
from models import User, Game, Turn
from models import UserRequestForm, StringMessage
from models import NewGameRequestForm, GameResultForm
from models import TurnRequestForm, TurnResultForm
from utils import get_by_urlsafe

CREATE_USER_REQUEST = endpoints.ResourceContainer(UserRequestForm)
NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameRequestForm)
TURN_REQUEST = endpoints.ResourceContainer(TurnRequestForm)

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
        if not User.is_email_valid(request.email):
            return StringMessage(
                message="Email address invalid! User is not created.")

        user = User(
            user_name = request.user_name,
            email = request.email)
        user.put()
        return StringMessage(message='User {} created!'.\
                             format(request.user_name))


    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameResultForm,
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
        game = Game.new_game(user.key, request.number_of_tiles.number,
                            request.dice_operation.name)

        # Add taskqueue here
        return game.to_form("Good luck playing Shut The Box, {}!".\
                           format(user.user_name))


    @endpoints.method(request_message=TURN_REQUEST,
                      response_message=TurnResultForm,
                      path='turn',
                      name='turn',
                      http_method='POST')
    def turn(self, request):
        game = get_by_urlsafe(request.urlsafe_key, Game)
        if game.game_over:
            recent_turn = game.most_recent_turn()
            return recent_turn.to_form(
                game_urlsafe_key=game.key.urlsafe(),
                valid_move=False,
                message="This game is already over.  Play again by calling " + "new_game()!")

        recent_turn = game.most_recent_turn()
        if not recent_turn:
            # If recent_turn is null, this is the first roll. It's only half a turn!
            turn = Turn.first_roll(game)
            return turn.to_form(
                game_urlsafe_key=game.key.urlsafe(),
                valid_move=True,
                message="Call turn() again to play your roll")

        if not request.flip_tiles:
            return recent_turn.to_form(
                game_urlsafe_key=game.key.urlsafe(),
                valid_move=False,
                message="User must pass in values to flip_tiles!")

        error = recent_turn.invalid_flip(request.flip_tiles,
                                         game.dice_operation)
        if error:
            return recent_turn.to_form(
                game_urlsafe_key=game.key.urlsafe(),
                valid_move=False,
                message=error)

        new_tiles = recent_turn.flip(request.flip_tiles)
        if not new_tiles:
            recent_turn.end_game(game)
            return recent_turn.to_form(
                game_urlsafe_key=game.key.urlsafe(),
                valid_move=True,
                message="Game over! Perfect score! Call new_game() to play again!")

        new_roll = recent_turn.new_roll(game)
        game_over = new_roll.is_game_over(game)
        if game_over:
            new_roll.end_game(game)
            return new_roll.to_form(
                game_urlsafe_key=game.key.urlsafe(),
                valid_move=True,
                message="Game over! Call new_game() to play again!")

        return new_roll.to_form(
            game_urlsafe_key=game.key.urlsafe(),
            valid_move=True,
            message="Call turn() again to play your roll")
