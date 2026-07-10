class ClickwrapError(Exception):
    """Base error for clickwrap/packet domain failures."""


class PacketNotFoundError(ClickwrapError):
    def __init__(self, packet_id: int | None = None) -> None:
        self.packet_id = packet_id
        message = f"Packet {packet_id} not found" if packet_id is not None else "Packet not found"
        super().__init__(message)


class PacketInvalidNameError(ClickwrapError):
    def __init__(self) -> None:
        super().__init__(
            "Clickthrough with the same name already exists. Please rename your clickthrough."
        )


class PacketPaginationError(ClickwrapError):
    def __init__(self) -> None:
        super().__init__("List Pagination out of range.")


class AgreementNotFoundError(ClickwrapError):
    def __init__(self, agreement_id: int | None = None) -> None:
        self.agreement_id = agreement_id
        message = (
            f"Agreement {agreement_id} not found"
            if agreement_id is not None
            else "Agreement not found"
        )
        super().__init__(message)
