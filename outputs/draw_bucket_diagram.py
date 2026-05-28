# -*- coding: utf-8 -*-
"""
Generate bucket structure diagram for patent disclosure.
Shows: adaptive buckets vs fixed-width buckets, with 4-point internal structure.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import numpy as np
import os

os.chdir(r'D:\work\hpc\outputs')

# Use Chinese font
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ── Generate sample data that mimics real GPU usage pattern ──
np.random.seed(42)
# Simulate ~200 data points over 100 time units
# Pattern: idle (0-30) → volatile training (30-55) → idle (55-65) → moderate (65-100)
t = np.linspace(0, 100, 200)
v = np.zeros(200)
# idle phase
v[0:60] = 5 + np.random.randn(60) * 2
# volatile training
v[60:110] = 50 + 30 * np.sin(np.linspace(0, 4*np.pi, 50)) + np.random.randn(50) * 8
# idle again
v[110:130] = 5 + np.random.randn(20) * 2
# moderate
v[130:200] = 35 + 15 * np.sin(np.linspace(0, 3*np.pi, 70)) + np.random.randn(70) * 5
v = np.clip(v, 0, 100)

# ── Simulate adaptive bucket partitioning ──
Tmax = 25     # max bucket width
Tmin = 2      # min window
Delta = 30    # fluctuation threshold

buckets = []
b_start = 0
b_min = v[0]
b_max = v[0]
first_val = v[0]
for i in range(1, len(t)):
    b_min = min(b_min, v[i])
    b_max = max(b_max, v[i])
    dt = t[i] - t[b_start]
    if dt > Tmax or (dt > Tmin and (b_max - b_min) > Delta):
        buckets.append({
            'start': int(b_start),
            'end': int(i),
            't_start': t[b_start],
            't_end': t[i],
            'first': first_val,
            'min': b_min,
            'max': b_max,
            'last': v[i],
        })
        b_start = i
        b_min = v[i]
        b_max = v[i]
        first_val = v[i]
# Add the last (open) bucket
if b_start < len(t) - 1:
    buckets.append({
        'start': int(b_start),
        'end': len(t) - 1,
        't_start': t[b_start],
        't_end': t[-1],
        'first': first_val,
        'min': b_min,
        'max': b_max,
        'last': v[-1],
    })

# ── Fixed-width buckets (10 time units each) for comparison ──
FW = 10
fixed_buckets = []
for bw_start in np.arange(0, 100, FW):
    mask = (t >= bw_start) & (t < bw_start + FW)
    if mask.sum() > 0:
        fixed_buckets.append({
            't_start': bw_start,
            't_end': bw_start + FW,
            'avg': v[mask].mean(),
        })

# ── Create the figure ──
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10),
                                 gridspec_kw={'height_ratios': [1.15, 1]})
fig.patch.set_facecolor('white')

# ═══════════════════════════════════════
# TOP: Adaptive buckets with 4-point trend
# ═══════════════════════════════════════
ax1.set_xlim(0, 100)
ax1.set_ylim(-5, 115)
ax1.set_xlabel('时间轴 (Time)', fontsize=12)
ax1.set_ylabel('GPU 使用率 (%)', fontsize=12)
ax1.set_title('本发明方案：写时增量双维度自适应桶划分 + 桶内4点多线段趋势还原',
              fontsize=14, fontweight='bold')

# Plot raw data as faint background
ax1.plot(t, v, color='#d0d0d0', linewidth=0.6, alpha=0.7, zorder=1)

# Color palette for buckets
colors = plt.cm.tab10(np.linspace(0, 1, len(buckets)))

# Draw each bucket
for idx, b in enumerate(buckets):
    color = colors[idx]
    bw = b['t_end'] - b['t_start']
    use_dense_hatch = (b['max'] - b['min']) > Delta

    # Bucket background with hatch for volatile buckets
    hatch = '//' if use_dense_hatch else ''
    alpha = 0.12 if use_dense_hatch else 0.06
    rect = mpatches.FancyBboxPatch(
        (b['t_start'], 0), bw, 105,
        boxstyle="round,pad=0",
        facecolor=color, edgecolor=color,
        linewidth=1.5 if use_dense_hatch else 0.8,
        alpha=alpha, hatch=hatch, zorder=2
    )
    ax1.add_patch(rect)

    # Bucket boundary lines
    ax1.axvline(x=b['t_start'], color=color, linewidth=0.8,
                linestyle='--', alpha=0.5, zorder=3)

    # 4-point positions (x coordinates)
    x0 = b['t_start']
    x1 = b['t_start'] + bw * 0.25
    x2 = b['t_start'] + bw * 0.75
    x3 = b['t_end']

    # Draw 4 feature points
    points_x = [x0, x1, x2, x3]
    points_y = [b['first'], b['min'], b['max'], b['last']]

    ax1.scatter(points_x, points_y, color=color, s=60, zorder=5,
                edgecolors='white', linewidth=1.2)

    # Draw 3 connecting segments
    ax1.plot([x0, x1], [b['first'], b['min']], color=color, linewidth=2.2, zorder=4)
    ax1.plot([x1, x2], [b['min'], b['max']], color=color, linewidth=2.2, zorder=4)
    ax1.plot([x2, x3], [b['max'], b['last']], color=color, linewidth=2.2, zorder=4)

    # Annotate bucket number
    mid_x = b['t_start'] + bw / 2
    ax1.annotate(f'桶{idx+1}\n{bw:.1f}h', xy=(mid_x, 108), fontsize=7,
                ha='center', va='bottom', color=color, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                         edgecolor=color, alpha=0.7))

# Legend for bucket coloring
ax1.axvline(x=buckets[-1]['t_end'], color='gray', linewidth=1.2,
            linestyle='-', alpha=0.8, zorder=3)

# Annotation for features
ax1.annotate('波动剧烈区域\n自动加密分桶\n(斜线填充)', xy=(42, 100), fontsize=9,
            ha='center', color='#c0392b',
            bbox=dict(boxstyle='round', facecolor='#fff5f5', edgecolor='#c0392b', alpha=0.9))
ax1.annotate('平稳区域\n自动拉长桶宽\n减少冗余', xy=(82, 100), fontsize=9,
            ha='center', color='#27ae60',
            bbox=dict(boxstyle='round', facecolor='#f5fff5', edgecolor='#27ae60', alpha=0.9))
ax1.annotate('空闲区域\n最宽桶', xy=(15, 100), fontsize=9,
            ha='center', color='#2980b9',
            bbox=dict(boxstyle='round', facecolor='#f5f9ff', edgecolor='#2980b9', alpha=0.9))

# ═══════════════════════════════════════
# BOTTOM: Traditional fixed-width single-point
# ═══════════════════════════════════════
ax2.set_xlim(0, 100)
ax2.set_ylim(-5, 115)
ax2.set_xlabel('时间轴 (Time)', fontsize=12)
ax2.set_ylabel('GPU 使用率 (%)', fontsize=12)
ax2.set_title('传统方案：固定宽度桶 + 每桶单点输出（平均值）',
              fontsize=14, fontweight='bold')

# Plot raw data as faint background
ax2.plot(t, v, color='#d0d0d0', linewidth=0.6, alpha=0.7, zorder=1)

# Draw fixed-width buckets
for idx, b in enumerate(fixed_buckets):
    color = '#7f8c8d'
    bw = b['t_end'] - b['t_start']

    rect = mpatches.FancyBboxPatch(
        (b['t_start'], 0), bw, 105,
        boxstyle="round,pad=0",
        facecolor=color, edgecolor=color,
        linewidth=0.8, alpha=0.05, zorder=2
    )
    ax2.add_patch(rect)

    ax2.axvline(x=b['t_start'], color=color, linewidth=0.6,
                linestyle='--', alpha=0.4, zorder=3)

    # Single average point at center
    mid_x = b['t_start'] + bw / 2
    ax2.scatter(mid_x, b['avg'], color=color, s=50, zorder=4,
                edgecolors='white', linewidth=1)

    # Connect successive avg points with straight lines
    if idx > 0:
        prev_mid = fixed_buckets[idx-1]['t_start'] + (fixed_buckets[idx-1]['t_end'] - fixed_buckets[idx-1]['t_start']) / 2
        ax2.plot([prev_mid, mid_x],
                [fixed_buckets[idx-1]['avg'], b['avg']],
                color=color, linewidth=1.5, zorder=3)

# Annotations
ax2.annotate('每桶宽度固定\n(均=10)', xy=(15, 100), fontsize=9,
            ha='center', color='#7f8c8d',
            bbox=dict(boxstyle='round', facecolor='white', edgecolor='#7f8c8d', alpha=0.8))
ax2.annotate('每桶仅1个均值点\n桶内波动完全丢失', xy=(65, 100), fontsize=9,
            ha='center', color='#e74c3c',
            bbox=dict(boxstyle='round', facecolor='#fff5f5', edgecolor='#e74c3c', alpha=0.9))

# ═══════════════════════════════════════
# Inset: zoom of a single bucket to show 4-point structure
# ═══════════════════════════════════════
# Pick a volatile bucket for zoom
volatile_bucket = None
for b in buckets:
    if (b['max'] - b['min']) > Delta and (b['t_end'] - b['t_start']) > 5:
        volatile_bucket = b
        break

if volatile_bucket:
    b = volatile_bucket
    # Add an inset axes on the top plot
    inset_ax = ax1.inset_axes([0.55, 0.35, 0.40, 0.40])

    # Get raw data within this bucket
    b_mask = (t >= b['t_start']) & (t <= b['t_end'])
    bt = t[b_mask]
    bv = v[b_mask]

    inset_ax.plot(bt, bv, color='#888888', linewidth=1.5, alpha=0.8, zorder=1)
    inset_ax.fill_between(bt, bv, alpha=0.1, color='#888888')

    bw = b['t_end'] - b['t_start']
    x_positions = [b['t_start'], b['t_start'] + bw*0.25, b['t_start'] + bw*0.75, b['t_end']]
    y_values = [b['first'], b['min'], b['max'], b['last']]
    labels = ['first_val', 'min_val', 'max_val', 'last_val']

    inset_ax.scatter(x_positions, y_values, color='#e74c3c', s=80, zorder=5,
                    edgecolors='white', linewidth=1.5)
    inset_ax.plot(x_positions, y_values, color='#e74c3c', linewidth=2.5, zorder=4)

    for xi, yi, lbl in zip(x_positions, y_values, labels):
        inset_ax.annotate(lbl, xy=(xi, yi), fontsize=8, fontweight='bold',
                         xytext=(0, 12), textcoords='offset points',
                         ha='center', color='#c0392b',
                         bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                                  edgecolor='#e74c3c', alpha=0.85))

    inset_ax.set_title('单桶放大：4点 → 3线段趋势还原', fontsize=10, fontweight='bold',
                       fontfamily='sans-serif', color='#c0392b')
    inset_ax.set_xlim(b['t_start'] - 0.5, b['t_end'] + 0.5)
    inset_ax.set_ylim(min(bv) - 8, max(bv) + 8)
    inset_ax.tick_params(labelsize=7)
    inset_ax.patch.set_facecolor('#fafafa')
    for spine in inset_ax.spines.values():
        spine.set_edgecolor('#e74c3c')
        spine.set_linewidth(1.2)

# Common adjustments
plt.tight_layout(pad=2.5)

# Save
output_path = 'bucket_structure_diagram.png'
fig.savefig(output_path, dpi=180, bbox_inches='tight', facecolor='white', edgecolor='none')
print(f'Saved: {output_path}')
plt.close()
