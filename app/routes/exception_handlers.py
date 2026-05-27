from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse,  HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from core import exceptions
from loguru import logger
import traceback

templates = Jinja2Templates(directory="app/templates")

def register_exception_handlers(app):
    '''
    Register various exception handlers
    '''
    
    # Redirect for login errors
    @app.exception_handler(exceptions.UnauthorizedException)
    async def unicorn_exception_handler(request: Request, exc: exceptions.UnauthorizedException):
        return RedirectResponse('/login')

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException
):
        '''
        Handle standard HTTP exceptions
        '''
        context = {
            'status_code':exc.status_code,
            'message': str(exc.detail),
        }
        return templates.TemplateResponse(request=request, name="error.html", context=context)


    @app.exception_handler(exceptions.BaseAppException)
    async def app_exc_handler(
        request: Request,
        exc: exceptions.BaseAppException,
    ):
        logger.error(f"Application Error ({exc.status_code}): {exc.message}")
        context = {
            'status_code':exc.status_code,
            'message': exc.message,
            }
        return templates.TemplateResponse(request=request, name="error.html", context=context)


    # Catchall - details to log only
    @app.exception_handler(Exception)
    async def catch_all_handler(request: Request, exc: Exception):
        # logger.error(
        #     "UnhandledException:\n%s"% 
        #     "".join(
        #         traceback.format_exception(
        #             type(exc),
        #             exc,
        #             exc.__traceback__,
        #         )
        #     )
        # )
        context = {
            'status_code':500,
            'message': "Something went wrong. Please try again later.",
            }
        return templates.TemplateResponse(request=request, name="error.html", context=context)

