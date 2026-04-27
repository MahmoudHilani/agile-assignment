from app.schemas.common import ApiError


def not_implemented_error(feature: str) -> ApiError:
    return ApiError(
        code="NOT_IMPLEMENTED",
        message=f"{feature} is reserved in this scaffold and has not been implemented yet.",
    )
