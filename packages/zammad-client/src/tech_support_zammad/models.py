from pydantic import BaseModel, Field


class TicketArticleInput(BaseModel):
    subject: str | None = None
    body: str
    type: str = "note"
    internal: bool = False
    content_type: str = "text/plain"


class CreateTicketRequest(BaseModel):
    title: str
    group: str
    customer_id: str = Field(description="Zammad customer id or guess:email pattern")
    priority: str | None = None
    article: TicketArticleInput
    tags: str | None = None


class TicketArticle(BaseModel):
    id: int
    ticket_id: int
    body: str | None = None
    subject: str | None = None


class Ticket(BaseModel):
    id: int
    number: str
    title: str
    group_id: int | None = None
    state_id: int | None = None
    priority_id: int | None = None
    owner_id: int | None = None
    customer_id: int | None = None

    model_config = {"extra": "allow"}


class TicketSearchResult(BaseModel):
    tickets: list[Ticket]
    count: int
