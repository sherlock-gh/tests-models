class AppError(Exception):
    def __init__(self, message, kind='bad_input'):
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.status = {'bad_input': 400, 'not_found': 404, 'rule_violation': 409}[kind]


def bad(message):
    raise AppError(message)


def missing(message):
    raise AppError(message, 'not_found')


def conflict(message):
    raise AppError(message, 'rule_violation')
