"""tasks.py - This file contains handlers that are called by cronjobs."""

import webapp2
import datetime
from models import User, Game
from collections import namedtuple
from google.appengine.api import mail, app_identity


class SendReminderEmail(webapp2.RequestHandler):
    def get(self):
        """If the User has not made a move in an active game for more than 12
        hours, send a reminder email that includes the current game state."""
        users = User.query(User.email != None).fetch()
        if users is None:
            return
        app_id = app_identity.get_application_id()
        twelve_hours_ago = datetime.datetime.now() - \
            datetime.timedelta(minutes=1)

        inactive_users = []
        GameData = namedtuple('GameData',
            ['urlsafe_key',
             'dice_operation', 'number_of_tiles',
             'game_start_datetime', 'last_turn_datetime',
             'active_tiles', 'roll', 'turn'])
        for n, user in enumerate(users):
            games_query = Game.query(ancestor=user.key)
            games_query = games_query.filter(Game.game_over == False)
            games_query = games_query.order(-Game.timestamp)
            games = games_query.fetch()
            # If games are not found, pass over this user
            if not games:
                continue
            inactive_games = []
            for game in games:
                recent_turn = game.most_recent_turn()
                # if the most recent turn is more recent than 12 hours ago,
                # pass over this game
                if recent_turn.timestamp > twelve_hours_ago:
                    continue
                game_data = GameData(
                    game.key.urlsafe(),
                    game.dice_operation, game.number_of_tiles,
                    game.timestamp, recent_turn.timestamp,
                    recent_turn.active_tiles, recent_turn.roll,
                    recent_turn.turn)
                inactive_games.append(game_data)
            if inactive_games:
                inactive_users.append([user, inactive_games])

        for inactive_user in inactive_users:
            user = inactive_user[0]
            games = inactive_user[1]
            number_of_games = len(games)

            subject = "This is a reminder!"
            salutation = """Hello, {0}.

You have incomplete game(s) of Shut The Box that have not progressed in over 12 hours.  This is a reminder to finish these incomplete games.

Number of incomplete games: {1}

            """.format(user.username, number_of_games)
            formatted_games = ""
            for game in games:
                formatted_games += """
                    urlsafe key: {0}
                    Last move: {1}
                    Game start: {2}
                    Active tiles: {3}
                    Most recent roll: {4}
                    Turn: {5}
                    Dice operation: {6}
                    Number of tiles: {7}

                    """.format(game.urlsafe_key,
                               game.last_turn_datetime,
                               game.game_start_datetime,
                               game.active_tiles,
                               game.roll,
                               game.turn,
                               game.dice_operation,
                               game.number_of_tiles)
            body = salutation + formatted_games
            mail.send_mail('noreply@{}.appspotmail.com'.format(app_id),
                           user.email,
                           subject,
                           body)


app = webapp2.WSGIApplication([
    ('/crons/send_reminder', SendReminderEmail)], debug=True)
