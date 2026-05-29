"""
Author: wadesmli
Date: 2026-06-01
Description: Logout page - clears cookie and redirects to login
"""
import dash
from dash import html, dcc

dash.register_page(__name__, path='/logout', name='退出登录')

layout = html.Div([
    dcc.Location(id='logout-url', refresh=True),
    html.Div('正在退出登录...', className='text-white text-center p-8')
])


def init_callbacks_logout(app):
    @app.callback(
        dash.Output('logout-url', 'pathname'),
        dash.Input('logout-url', 'pathname')
    )
    def handle_logout(pathname):
        if pathname == '/logout':
            # 清除 cookie
            dash.callback_context.response.set_cookie(
                'access_token',
                '',
                expires=0,
                httponly=True,
                samesite='lax',
                path='/'
            )
            return '/login'
        return dash.no_update
