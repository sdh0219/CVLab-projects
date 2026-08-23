import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from code.data_loader import load_earthquake_events, save_processed_data
from code.data_cleaner import clean_earthquake_data
from code.visualization import generate_earthquake_charts


def main():
    print('=' * 60)
    print('基于真实地震数据的个性化地震预警信息自动生成系统')
    print('=' * 60)

    print('\n[1/4] 读取真实地震事件数据...')
    df_raw = load_earthquake_events()
    if df_raw.empty:
        print('      错误：未找到地震事件数据，请先运行 crawler/update_earthquake_data.py')
        sys.exit(1)
    print(f'      共读取 {len(df_raw)} 条真实地震记录')

    print('\n[2/4] 清洗真实地震数据...')
    df_clean = clean_earthquake_data(df_raw)
    print(f'      清洗后剩余 {len(df_clean)} 条有效记录')

    print('\n[3/4] 保存处理后的地震数据...')
    path = save_processed_data(df_clean)
    print(f'      已保存至: {path}')

    print('\n[4/4] 生成地震统计图表...')
    chart_paths = generate_earthquake_charts(df_clean)
    for name, cpath in chart_paths.items():
        full_path = os.path.join(os.path.dirname(__file__), 'static', cpath)
        print(f'      {name}: {full_path}')

    print(f'\n{"=" * 60}')
    print(f'处理完成！共 {len(df_clean)} 条真实地震事件记录，{len(chart_paths)} 张统计图。')
    print('=' * 60)


if __name__ == '__main__':
    main()
