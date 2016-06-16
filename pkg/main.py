import logging
from pkg import *
from models import User, Game, Turn
from models import CreateUserRequestForm, StringMessage
from models import NewGameRequestForm, GameResultForm
from models import TurnRequestForm, TurnResultForm
from models import UserRequestForm, UserStatsResultForm
from models import AllGamesForm, GamesStatusResultForm
from models import PlayByPlayRequestForm, TurnsStatusForm
from models import LeaderboardRequestForm, LeaderboardsResultForm
from models import LeaderboardResultForm
from utils import get_by_urlsafe
from collections import namedtuple
from operator import attrgetter

CREATE_USER_REQUEST = endpoints.ResourceContainer(CreateUserRequestForm)
NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameRequestForm)
TURN_REQUEST = endpoints.ResourceContainer(TurnRequestForm)
USER_REQUEST = endpoints.ResourceContainer(UserRequestForm)
ALL_GAMES_REQUEST = endpoints.ResourceContainer(AllGamesForm)
PLAY_BY_PLAY_REQUEST = endpoints.ResourceContainer(PlayByPlayRequestForm)
LEADERBOARD_REQUEST = endpoints.ResourceContainer(LeaderboardRequestForm)

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
                message="Email address invalid according to MailGun! User is not created.")

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
        return game.to_game_result_form("Good luck playing Shut The Box, {}!".\
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

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=UserStatsResultForm,
                      path='user_stats',
                      name='user_stats',
                      http_method='POST')
    def user_stats(self, request):
        user = User.query(User.user_name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A user with the name {} does not exist!'.\
                    format(request.user_name))

        games_query = Game.query(ancestor=user.key)
        games_query = games_query.filter(Game.game_over == True)

        if request.number_of_tiles:
            games_query = games_query.filter(
                Game.number_of_tiles == request.number_of_tiles.number)

        if request.dice_operation:
            games_query = games_query.filter(
                Game.dice_operation == request.dice_operation.name)

        games = games_query.fetch()
        if not games:
            return UserStatsResultForm(message="No games found!")

        (games_played, cumulative_score, cumulative_number_of_turns,
            average_score, average_number_of_turns) = Game.games_stats(games)


        form =  UserStatsResultForm(
            games_played=games_played,
            cumulative_score=cumulative_score,
            cumulative_number_of_turns=cumulative_number_of_turns,
            average_score=average_score,
            average_number_of_turns=average_number_of_turns,
            message="Games found!")
        if request.dice_operation:
            form.message += " | Filter: dice_operation == {}"\
                .format(request.dice_operation.name)
        if request.number_of_tiles:
            form.message += " | Filter: number_of_tiles == {}"\
                .format(request.number_of_tiles.number)
        return form


    @endpoints.method(request_message=ALL_GAMES_REQUEST,
                      response_message=GamesStatusResultForm,
                      path='all_games',
                      name='all_games',
                      http_method='POST')
    def all_games(self, request):
        if request.user_name:
            user = User.query(User.user_name == request.user_name).get()
            if not user:
                raise endpoints.NotFoundException(
                        'A user with the name {} does not exist!'.\
                        format(request.user_name))
            games_query = Game.query(ancestor=user.key)
        else:
            games_query = Game.query()

        if request.only_open_games == True \
            and request.only_completed_games == True:
            raise endpoints.BadRequestException("Method all_games can't be called with the parameters only_open_games and only_completed_games both True")

        if request.only_open_games:
            games_query = games_query.filter(Game.game_over == False)
        if request.only_completed_games:
            games_query = games_query.filter(Game.game_over == True)

        games_query = games_query.order(-Game.timestamp)
        games = games_query.fetch()

        return GamesStatusResultForm(
            items=[game.to_game_status_result_form() for game in games])


    @endpoints.method(request_message=PLAY_BY_PLAY_REQUEST,
                      response_message=TurnsStatusForm,
                      path='play_by_play',
                      name='play_by_play',
                      http_method='POST')
    def play_by_play(self, request):
        game = get_by_urlsafe(request.urlsafe_key, Game)
        turns = Turn.query(ancestor=game.key).order(Turn.timestamp).fetch()
        return TurnsStatusForm(
            items=[turn.to_turn_status_form() for turn in turns])

# class LeaderboardRequestForm(messages.Message):
#     number_of_tiles = messages.EnumField('NumberOfTiles', 1)
#     dice_operation = messages.EnumField('DiceOperation', 2)
#     use_total_score = messages.BooleanField(3, default=True)
#     use_average_game_score = messages.BooleanField(4, default=False)
#
#
# class LeaderBoardResultForm(messages.Message):
#     user_name = messages.StringField(1, required=True)
#     total_score = messages.IntegerField(2)
#     average_score = messages.IntegerField(3)
#     games_played = messages.IntegerField(4)
#
#
# class LeaderBoardsResultForm(messages.Message):
#     items = messages.MessageField(LeaderBoardResultForm, 1, repeated=True)
#     filters = messages.StringField(2)
    @endpoints.method(request_message=LEADERBOARD_REQUEST,
                      response_message=LeaderboardsResultForm,
                      path='leaderboard',
                      name='leaderboard',
                      http_method='POST')
    def leaderboard(self, request):
        users = User.query().fetch()
        if not users:
            return LeaderboardsResultForm(message="No users created yet!")
        logging.warning(users)
        users = iter(users)
        leaderboard = []
        UserStats = namedtuple('UserStats',
            ['score', 'games_played', 'user_name'])
        for user in users:
            games_query = Game.query(ancestor=user.key)
            games_query = games_query.filter(Game.game_over == True)

            if request.number_of_tiles:
                games_query = games_query.filter(
                    Game.number_of_tiles == request.number_of_tiles.number)

            if request.dice_operation:
                games_query = games_query.filter(
                    Game.dice_operation == request.dice_operation.name)

            games = games_query.fetch()
            if not games:
                continue
            (games_played, cumulative_score,
                cumulative_number_of_turns, average_score,
                average_number_of_turns) = Game.games_stats(games)


            if request.use_cumulative_score:
                user_stats = UserStats(
                    float(cumulative_score), games_played, user.user_name)
            else:
                user_stats = UserStats(
                    average_score, games_played, user.user_name)
            leaderboard.append(user_stats)

        if not leaderboard:
            return LeaderboardsResultForm(message="No games played yet!")
        # Now to sort the results
        logging.warning(leaderboard)
        leaderboard.sort(key=attrgetter('score'))
        logging.warning(leaderboard)

        forms  = []
        for user in leaderboard:
            leaderboard_form = LeaderboardResultForm(
                user_name=user.user_name,
                games_played=user.games_played,
                score=user.score)
            forms.append(leaderboard_form)
        message = "Users Found!"
        if request.dice_operation:
            message += " | Filter: dice_operation == {}"\
                .format(request.dice_operation.name)
        if request.number_of_tiles:
            message += " | Filter: number_of_tiles == {}"\
                .format(request.number_of_tiles.number)
        if request.use_cumulative_score:
            message += " | use_cumulative_score == True"
        return LeaderboardsResultForm(items=forms, message=message)
