from src.models import AuditLog
def record(db,actor,action,detail): db.add(AuditLog(actor=actor,action=action,detail=detail))
