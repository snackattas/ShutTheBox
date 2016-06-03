from pkg import *
from models import Turn
from random import choice


def get_by_urlsafe(urlsafe, model):
    """Returns an ndb.Model entity that the urlsafe key points to. Checks
        that the type of entity returned is of the correct kind. Raises an
        error if the key String is malformed or the entity is of the incorrect
        kind
    Args:
        urlsafe: A urlsafe key string
        model: The expected entity kind
    Returns:
        The entity that the urlsafe Key string points to or None if no entity
        exists.
    Raises:
        ValueError:"""
    try:
        key = ndb.Key(urlsafe=urlsafe)
    except TypeError:
        raise endpoints.BadRequestException('Invalid Key')
    except Exception, e:
        if e.__class__.__name__ == 'ProtocolBufferDecodeError':
            raise endpoints.BadRequestException('Invalid Key')
        else:
            raise


    entity = key.get()
    if not entity:
        return None
    if not isinstance(entity, model):
        raise ValueError('Incorrect Kind')
    return entity


def roll_dice(active_tiles):
    if six_above_deactivated(active_tiles):
        return [choice(range(1, 7))]
    return [choice(range(1, 7)), choice(range(1, 7))]


def six_above_deactivated(active_tiles):
    if filter(lambda n: n>5, active_tiles):
        return False
    return True


def most_recent_turn(game_key):
    return Turn.query(ancestor=game_key).order(-Turn.timestamp).get()


def create_turn_key(game_key):
    turn_id = Turn.allocate_ids(size=1, parent=game_key)[0]
    return ndb.Key(Turn, turn_id, parent=game_key)
