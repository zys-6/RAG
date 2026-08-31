import redis

from utils.utils import read_yaml


class RedisClient:

    def __init__(self, config_path: str, config_name: str = 'redis_config'):
        self.config = read_yaml(config_path, config_name)
        self.client = redis.StrictRedis(self.config['host'],
                                        self.config['port'],
                                        self.config['database'])

    def hset(self, name, key, val):
        self.client.hset(name, key, val)

    def hget(self, name, key):
        return self.client.hget(name, key)

    def hdel(self, name, key):
        self.client.hdel(name, key)

    def hgetall(self, name, key=None):
        ret = {}
        for item in self.client.hscan_iter(name, match=key):
            ret[item[0]] = item[1]
        return ret
