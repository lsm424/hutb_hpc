'''
Author: wadesmli
Date: 2026-06-01 15:55:32
LastEditors: wadesmli
LastEditTime: 2026-06-01 15:56:01
FilePath: matplotlib_config.py
Description: Matplotlib 中文字体配置模块 解决中文乱码问题

Copyright (c) 2026 by wadesmli, All Rights Reserved. 
'''
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


def setup_chinese_font():
    """设置matplotlib支持中文显示"""
    # 尝试设置中文字体（按优先级）
    chinese_fonts = ['SimHei', 'Microsoft YaHei', 'SimSun', 'KaiTi', 'FangSong']

    available_fonts = [f.name for f in fm.fontManager.ttflist]
    selected_font = None

    for font in chinese_fonts:
        if font in available_fonts:
            selected_font = font
            break

    if selected_font:
        plt.rcParams['font.sans-serif'] = [selected_font, 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
        return selected_font
    else:
        # 如果没有中文字体，使用英文标签
        return None


def get_font_info():
    """获取当前字体配置信息"""
    return {
        'sans-serif': plt.rcParams.get('font.sans-serif', 'Not set'),
        'axes.unicode_minus': plt.rcParams.get('axes.unicode_minus', 'Not set')
    }
