"""
=============================================
⚠️ 统一异常处理模块
=============================================
模块名称: error_handler.py
模块功能:
    - 全局异常处理器
    - 参数校验异常处理器
    - 错误响应格式统一
    - 敏感信息脱敏
"""

import traceback
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.logger import log


class ErrorResponse:
    """错误响应格式"""

    @staticmethod
    def create(error_code: str, message: str, status_code: int = 500) -> JSONResponse:
        """
        创建标准错误响应

        Args:
            error_code: 错误码
            message: 错误信息（用户友好）
            status_code: HTTP 状态码

        Returns:
            JSONResponse: 标准格式的错误响应
        """
        return JSONResponse(
            status_code=status_code,
            content={
                "code": error_code,
                "msg": message,
                "data": None
            }
        )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局异常处理器

    捕获所有未处理的异常，返回安全的错误信息

    Args:
        request: FastAPI 请求对象
        exc: 异常对象

    Returns:
        JSONResponse: 标准错误响应
    """
    # 记录完整错误到日志（包含堆栈）
    log.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")

    # 返回安全错误信息（不泄露内部细节）
    return ErrorResponse.create(
        error_code="INTERNAL_ERROR",
        message="服务内部错误，请稍后重试",
        status_code=500
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    参数校验异常处理器

    处理请求参数验证失败的情况

    Args:
        request: FastAPI 请求对象
        exc: 验证异常对象

    Returns:
        JSONResponse: 标准错误响应
    """
    # 记录验证错误
    log.warning(f"Validation error: {exc.errors()}")

    # 提取第一个错误字段
    errors = exc.errors()
    if errors:
        field = errors[0].get("loc", ["unknown"])[-1]
        msg = errors[0].get("msg", "validation failed")
        error_msg = f"参数 '{field}' {msg}"
    else:
        error_msg = "请求参数不正确"

    return ErrorResponse.create(
        error_code="VALIDATION_ERROR",
        message=error_msg,
        status_code=400
    )


async def http_exception_handler(request: Request, exc) -> JSONResponse:
    """
    HTTP 异常处理器

    处理 HTTPException，确保返回统一格式

    Args:
        request: FastAPI 请求对象
        exc: HTTPException 对象

    Returns:
        JSONResponse: 标准错误响应
    """
    return ErrorResponse.create(
        error_code="HTTP_ERROR",
        message=exc.detail,
        status_code=exc.status_code
    )


# ==========================================
# 📤 导出对象
# ==========================================

__all__ = [
    "ErrorResponse",
    "global_exception_handler",
    "validation_exception_handler",
    "http_exception_handler",
]
