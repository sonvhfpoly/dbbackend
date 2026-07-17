from fastapi import HTTPException, status

# Subclassing HTTPException (rather than a plain Exception) means services can
# raise these directly and FastAPI turns them into the right JSON response
# without a router needing its own try/except per error case.
class BusinessLogicException(HTTPException):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=message)

class EntityNotFoundException(BusinessLogicException):
    def __init__(self, entity: str, entity_id: any):
        super().__init__(
            message=f"{entity} with id {entity_id} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )

class UnauthorizedException(BusinessLogicException):
    def __init__(self, message: str = "Could not validate credentials"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )
