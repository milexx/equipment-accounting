import enum


class UserRole(str, enum.Enum):
    region = "region"
    center = "center"
    center_admin = "center_admin"


class EquipmentStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    needs_revision = "needs_revision"
    accepted = "accepted"
    diagnostics_required = "diagnostics_required"
    writeoff_review = "writeoff_review"
    writeoff_approved = "writeoff_approved"
    disposal_pending = "disposal_pending"
    disposed = "disposed"
    valuation_pending = "valuation_pending"
    valued = "valued"
    sale_ready = "sale_ready"
    listed_for_sale = "listed_for_sale"
    sold = "sold"
    archived = "archived"
    deleted = "deleted"


class EquipmentCondition(str, enum.Enum):
    unknown = "unknown"
    working = "working"
    broken = "broken"
    partially_working = "partially_working"
    requires_diagnostics = "requires_diagnostics"


class EquipmentDisposition(str, enum.Enum):
    undecided = "undecided"
    writeoff = "writeoff"
    disposal = "disposal"
    valuation = "valuation"
    sale = "sale"


class EquipmentSaleStatus(str, enum.Enum):
    not_for_sale = "not_for_sale"
    valuation_pending = "valuation_pending"
    priced = "priced"
    ready = "ready"
    listed = "listed"
    reserved = "reserved"
    sold = "sold"


class EquipmentFieldType(str, enum.Enum):
    string = "string"
    text = "text"
    integer = "integer"
    decimal = "decimal"
    date = "date"
    boolean = "boolean"
    select = "select"
    multiselect = "multiselect"


class EquipmentPhotoPurpose(str, enum.Enum):
    general = "general"
    serial = "serial"
    defect = "defect"
    completeness = "completeness"
    other = "other"
