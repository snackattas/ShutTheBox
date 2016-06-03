import logging
from pkg import *
from models import User, Game, Turn
from models import UserRequestForm, StringMessage
from models import NewGameRequestForm, GameResultForm
from models import TurnRequestForm, TurnResultForm

from utils import get_by_urlsafe, most_recent_turn, create_turn_key, roll_dice

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
        game_id = Game.allocate_ids(size=1, parent=user.key)[0]
        game_key = ndb.Key(Game, game_id, parent=user.key)
        game = Game(
            key=game_key,
            number_of_tiles=request.number_of_tiles.number,
            dice_operation=request.dice_operation.name)
        game.put()
        # Add taskqueue here
        return GameResultForm(
            urlsafe_key=game_key.urlsafe(),
            active_tiles=range(1, request.number_of_tiles.number+1),
            dice_operation=request.dice_operation.name,
            message="Good luck playing Shut The Box, {}!".\
                    format(user.user_name))


    @endpoints.method(request_message=TURN_REQUEST,
                      response_message=TurnResultForm,
                      path='turn',
                      name='turn',
                      http_method='POST')
    def turn(self, request):
        game = get_by_urlsafe(request.urlsafe_key, Game)
        if game.game_over:
            return TurnResultForm(
                urlsafe_key=request.urlsafe_key,
                game_over=True,
                message="This game is already over.  Play again by calling new_game()!")

        recent_turn = most_recent_turn(game.key)
        if not recent_turn:
            # If recent_turn is null, this is the first roll/turn.
            if request.flip_tiles:
                return TurnResultForm(
                    urlsafe_key=request.urlsafe_key,
                    message="This is the first turn! Call turn() first without flipping any tiles, so you receive a roll and can know which tiles you can flip!")
            active_tiles = range(1, game.number_of_tiles+1)
            roll = roll_dice(active_tiles)
            turn = Turn(
                key=create_turn_key(game.key),
                turn=1,
                roll=roll,
                active_tiles=active_tiles)
            turn.put()
            return TurnResultForm(
                urlsafe_key=request.urlsafe_key,
                roll=roll,
                active_tiles=active_tiles,
                score=sum(active_tiles),
                message="Call turn() again to play your roll")

        active_tiles = recent_turn.active_tiles
        roll = recent_turn.roll
        turn_counter = recent_turn.turn

        if not request.flip_tiles:
            return TurnResultForm(
                urlsafe_key=request.urlsafe_key,
                roll=roll,
                active_tiles=active_tiles,
                message="User must pass in values in flip_tiles!")

        error = recent_turn.invalid_flip(request.flip_tiles,
                                         active_tiles,
                                         roll,
                                         game.dice_operation)
        if error:
            return TurnResultForm(
                urlsafe_key=request.urlsafe_key,
                roll=roll,
                active_tiles=active_tiles,
                valid_move=False,
                score=sum(active_tiles),
                message=error)

        for tile in request.flip_tiles:
            active_tiles.remove(tile)
        recent_turn.active_tiles = active_tiles
        # check for a perfect score here
        if not active_tiles:
            recent_turn.game_over = True
            recent_turn.put()

            game.game_over = True
            game.final_score = 0
            game.put()

            return TurnResultForm(
                urlsafe_key=request.urlsafe_key,
                score=0,
                game_over=True,
                valid_move=True,
                message="Game over! Perfect score! Call new_game() to play again!")
        recent_turn.put()

        new_roll = roll_dice(active_tiles)
        new_turn = Turn(
            key=create_turn_key(game.key),
            turn=turn_counter + 1,
            roll=new_roll,
            active_tiles=active_tiles)

        if game.dice_operation == "ADDITION":
            roll_total = sum(new_roll)
            valid_rolls = new_turn.valid_roll_combos(active_tiles, 12)
        if game.dice_operation == "MULTIPLICATION":
            roll_total = new_turn.multiply(new_roll)
            valid_rolls = new_turn.valid_roll_combos(active_tiles, 36)

        score = sum(active_tiles)
        if roll_total not in valid_rolls:
            new_turn.game_over = True
            new_turn.put()

            game.game_over = True
            game.final_score = score
            game.put()

            return TurnResultForm(
                urlsafe_key=request.urlsafe_key,
                roll=new_roll,
                active_tiles=active_tiles,
                score=score,
                game_over=True,
                message="Game over! Call new_game() to play again!")

        new_turn.put()
        return TurnResultForm(
            urlsafe_key=request.urlsafe_key,
            roll=new_roll,
            active_tiles=active_tiles,
            valid_move=True,
            score=score,
            message="Valid move! Call turn() to play your new roll!")
