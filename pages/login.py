"""
Author: wadesmli
Date: 2026-05-29
Description: Login page for HPC Dashboard
"""
import dash
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta

dash.register_page(__name__, path='/login', name='登录')

layout = html.Div([
    dcc.Location(id='login-url', refresh=True),

    html.Div([
        html.Div([
            html.Div([
                html.Img(src='/assets/logo.jpg', className='rounded-xl mb-6 mx-auto shadow-lg', style={'width': 'auto', 'height': '64px', 'objectFit': 'contain'}),
                html.H1('HPC管理系统', className='text-3xl font-bold text-white mb-2 text-center tracking-wide'),
                html.P('高性能计算集群监控平台', className='text-gray-500 text-sm text-center mb-8')
            ]),

            dbc.Form([
                html.Div([
                    html.Label('用户名', className='text-gray-400 text-sm font-medium mb-2 block'),
                    dbc.Input(
                        id='login-username',
                        type='text',
                        placeholder='请输入用户名',
                        className='bg-gray-800/50 border-gray-700 text-white placeholder-gray-600',
                        style={
                            'width': '100%',
                            'padding': '12px 16px',
                            'borderRadius': '10px',
                            'border': '1px solid #374151',
                            'fontSize': '14px',
                            'transition': 'all 0.2s'
                        },
                        autocomplete='username'
                    )
                ], className='mb-4'),

                html.Div([
                    html.Label('密码', className='text-gray-400 text-sm font-medium mb-2 block'),
                    dbc.Input(
                        id='login-password',
                        type='password',
                        placeholder='请输入密码',
                        className='bg-gray-800/50 border-gray-700 text-white placeholder-gray-600',
                        style={
                            'width': '100%',
                            'padding': '12px 16px',
                            'borderRadius': '10px',
                            'border': '1px solid #374151',
                            'fontSize': '14px',
                            'transition': 'all 0.2s'
                        },
                        autocomplete='current-password'
                    )
                ], className='mb-6'),

                html.Div(id='login-error', className='text-red-400 text-sm mb-4 text-center font-medium'),

                dbc.Button(
                    '登 录',
                    id='login-button',
                    color='primary',
                    className='w-100 font-semibold',
                    style={
                        'width': '100%',
                        'padding': '12px',
                        'borderRadius': '10px',
                        'fontSize': '15px',
                        'letterSpacing': '2px',
                        'background': 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                        'border': 'none',
                        'boxShadow': '0 4px 14px rgba(37, 99, 235, 0.3)',
                        'transition': 'all 0.2s'
                    },
                    n_clicks=0
                )
            ]),

        ], style={
            'width': '100%',
            'maxWidth': '400px',
            'padding': '48px 40px',
            'background': 'rgba(17, 24, 39, 0.85)',
            'backdropFilter': 'blur(20px)',
            'borderRadius': '20px',
            'border': '1px solid rgba(55, 65, 81, 0.5)',
            'boxShadow': '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
        })
    ], style={
        'minHeight': '100vh',
        'display': 'flex',
        'alignItems': 'center',
        'justifyContent': 'center',
        'background': 'linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)',
        'padding': '20px'
    })
])


def init_callbacks_login(app):
    @app.callback(
        [Output('login-url', 'pathname'),
         Output('login-error', 'children')],
        [Input('login-button', 'n_clicks')],
        [State('login-username', 'value'),
         State('login-password', 'value')],
        prevent_initial_call=True
    )
    def handle_login(n_clicks, username, password):
        if not n_clicks:
            return dash.no_update, dash.no_update

        if not username or not password:
            return dash.no_update, '请输入用户名和密码'

        from service.auth import USERS, create_access_token

        user = USERS.get(username)
        if not user or user['password'] != password:
            return dash.no_update, '用户名或密码错误'

        access_token = create_access_token(
            data={'sub': username, 'role': user['role'], 'name': user['name']}
        )

        expires = datetime.now() + timedelta(hours=8)
        dash.callback_context.response.set_cookie(
            'access_token',
            access_token,
            expires=expires,
            httponly=True,
            samesite='lax',
            path='/'
        )

        return '/', ''
