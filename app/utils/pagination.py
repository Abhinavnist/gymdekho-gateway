from dataclasses import dataclass
from typing import Any


@dataclass
class PaginationParams:
    page: int = 1
    limit: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit

    def validate(self) -> "PaginationParams":
        self.page = max(1, self.page)
        self.limit = min(max(1, self.limit), 100)  # cap at 100 per page
        return self


def paginated_response(
    data: list[Any],
    total: int,
    page: int,
    limit: int,
) -> dict:
    total_pages = (total + limit - 1) // limit
    return {
        "data": data,
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }
