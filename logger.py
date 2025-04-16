
class Logger:
    # Logger constructor
    # `source`: label for each log message
    # `level`: log level; defaults to 3 (error)
    loglevel = {
        '0': 'debug',
        '1': 'info',
        '2': 'warn',
        '3': 'error',
        '4': 'critical',
    }
    def __init__(self, source: str, level: int = 3):
        if level < 0 or level > 4:
            raise Exception('Invalid log level, must be int in [0,4]')
        self.level = level
        
        if source is not None:
            self.source = source
        else:
            raise Exception('Source must not be None')

    def log(self, msg: str, level: int = 0):
        if (level > self.level):
            print(f'{self.source} {self.loglevel[str(level).upper()]}: {msg}')

    def debug(self, msg: str):
        self.log(msg, 0)

    def info(self, msg: str):
        self.log(msg, 1)

    def warn(self, msg: str):
        self.log(msg, 2)

    def error(self, msg: str):
        self.log(msg, 3)

    def critical(self, msg: str):
        self.log(msg, 4)
