"""
统一业务异常体系
"""

from typing import Any, Optional

class BusinessException(Exception):
    def __init__(self, code: int = 400, message: str = "业务异常", data: Optional[Any] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

class TenantAccessDeniedException(BusinessException):
    def __init__(self, message: str = "跨租户访问被拒绝"):
        super().__init__(code=403, message=message)

class ComplianceBlockedException(BusinessException):
    def __init__(self, message: str = "命中合规红线禁词，生成被阻断", data: Optional[Any] = None):
        super().__init__(code=422, message=message, data=data)
