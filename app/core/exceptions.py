from fastapi import HTTPException, status


class AppException(HTTPException):
    def __init__(self, status_code: int, detail: str, error_code: str = "ERROR"):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code


# ─── Auth ────────────────────────────────────────────────────────────────────

class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Authentication required."):
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail, "UNAUTHORIZED")


class ForbiddenException(AppException):
    def __init__(self, detail: str = "You do not have permission to perform this action."):
        super().__init__(status.HTTP_403_FORBIDDEN, detail, "FORBIDDEN")


class InvalidCredentialsException(AppException):
    def __init__(self):
        super().__init__(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.", "INVALID_CREDENTIALS")


class AccountLockedException(AppException):
    def __init__(self):
        super().__init__(status.HTTP_423_LOCKED, "Account is temporarily locked due to multiple failed attempts.", "ACCOUNT_LOCKED")


class EmailNotVerifiedException(AppException):
    def __init__(self):
        super().__init__(status.HTTP_403_FORBIDDEN, "Please verify your email address first.", "EMAIL_NOT_VERIFIED")


# ─── Resource ────────────────────────────────────────────────────────────────

class NotFoundException(AppException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(status.HTTP_404_NOT_FOUND, f"{resource} not found.", "NOT_FOUND")


class AlreadyExistsException(AppException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(status.HTTP_409_CONFLICT, f"{resource} already exists.", "ALREADY_EXISTS")


class ValidationException(AppException):
    def __init__(self, detail: str):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, "VALIDATION_ERROR")


# ─── Business ────────────────────────────────────────────────────────────────

class SubscriptionLimitException(AppException):
    def __init__(self, detail: str = "You have reached your plan limit. Please upgrade."):
        super().__init__(status.HTTP_402_PAYMENT_REQUIRED, detail, "SUBSCRIPTION_LIMIT")


class GymNotApprovedException(AppException):
    def __init__(self):
        super().__init__(status.HTTP_403_FORBIDDEN, "Your gym is pending admin approval.", "GYM_NOT_APPROVED")


# ─── Server ──────────────────────────────────────────────────────────────────

class DatabaseException(AppException):
    def __init__(self, detail: str = "A database error occurred."):
        super().__init__(status.HTTP_500_INTERNAL_SERVER_ERROR, detail, "DB_ERROR")
