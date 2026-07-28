import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="LoL Match Analytics", layout="wide")

# ─── Загрузка и кэширование ───
@st.cache_data
def load_data():
    matches = '''
    SELECT
      *,
      CASE
        WHEN STARTS_WITH(match_id, 'NA1_') THEN 'americas'
        ELSE 'europe'
      END AS region
    FROM read_parquet('data/matches.parquet')
    '''
    matches = duckdb.query(matches).to_df()
    matches['duration_min'] = round(matches['game_duration_sec'] / 60)
    matches['win_num'] = matches['win'].astype(int)
    # Построчный KDA (исправлено)
    matches['kda'] = (matches['kills'] + matches['assists']) / matches['deaths'].replace(0, 1)

    players = duckdb.query("SELECT * FROM read_parquet('data/players.parquet')").to_df()
    items   = duckdb.query("SELECT * FROM read_parquet('data/items.parquet')").to_df()

    item_cols = ['item0', 'item1', 'item2', 'item3', 'item4', 'item5']
    item_dict = dict(zip(items['item_id'], items['item_name']))
    for col in item_cols:
        matches[col] = matches[col].fillna(0).astype(int).astype(str).map(item_dict)

    items_full = pd.melt(matches, id_vars=['win', 'team_position'],
                         value_vars=[f'item{i}' for i in range(6)],
                         var_name='slot', value_name='item_id')
    items_full = items_full[items_full['item_id'] != 0]

    win_items = items_full[items_full['win'] == True]['item_id']
    top10 = win_items.value_counts().head(10).reset_index()
    top10.columns = ['item_id', 'count']

    role_counts = items_full[items_full['win'] == True] \
        .groupby(['team_position', 'item_id']).size().reset_index(name='count')
    role_top5 = role_counts.sort_values(['team_position', 'count'], ascending=[True, False]) \
                           .groupby('team_position').head(5).reset_index(drop=True)

    POSITIONS = matches['team_position'].dropna().unique().tolist()
    POS_COLORS = {'TOP': '#ef4444', 'JUNGLE': '#22c55e', 'MIDDLE': '#3b82f6',
                  'BOTTOM': '#f59e0b', 'UTILITY': '#a855f7'}

    return matches, players, role_top5, top10, POSITIONS, POS_COLORS


matches, players, role_top5, top10, POSITIONS, POS_COLORS = load_data()

st.title("Анализ матчей League of Legends")

# ─── Фильтры (боковая панель) ───
with st.sidebar:
    st.header("Фильтры")
    selected_regions = st.multiselect(
        "Регион",
        options=sorted(matches['region'].unique()),
        default=['europe', 'americas']
    )
    selected_positions = st.multiselect(
        "Роль",
        options=POSITIONS,
        default=POSITIONS
    )
    selected_win = st.selectbox(
        "Исход матча",
        options=['all', 1, 0],
        format_func=lambda x: {1: 'Победа', 0: 'Поражение', 'all': 'Все'}[x]
    )

# ─── Применение фильтров ───
chart_data = matches[matches['region'].isin(selected_regions)]
chart_data = chart_data[chart_data['team_position'].isin(selected_positions)]
if selected_win != 'all':
    chart_data = chart_data[chart_data['win_num'] == selected_win]

chart_data_players = players.copy()
if 'region_api' in chart_data_players.columns:
    chart_data_players = chart_data_players[chart_data_players['region_api'].isin(selected_regions)]

champion_group = chart_data.groupby('champion')['win_num'].agg(['count', 'sum']).reset_index()

# ─── Вкладки ───
tab1, tab2, tab3 = st.tabs(["Общий срез и KPI", "Герои и Роли", "Статистика"])

# ═══ TAB 1 ═══
with tab1:
    # KPI
    total_matches = chart_data['match_id'].count()
    mean_kda = round((chart_data['kills'].mean() + chart_data['assists'].mean()) / chart_data['deaths'].mean(), 2)
    duration_mean = round(chart_data['duration_min'].mean())

    k1, k2, k3 = st.columns(3)
    with k1:
        fig = go.Figure(go.Indicator(
            value=int(total_matches),
            number={'font': {'size': 48, 'color': '#60a5fa'}}
        ))
        fig.update_layout(title="Количество матчей", paper_bgcolor='rgba(0,0,0,0)',
                          plot_bgcolor='rgba(0,0,0,0)', height=150,
                          margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True, key="kpi_total")
    with k2:
        fig = go.Figure(go.Indicator(
            value=mean_kda,
            number={'font': {'size': 48, 'color': '#fbbf24'}}
        ))
        fig.update_layout(title="Среднее KDA", paper_bgcolor='rgba(0,0,0,0)',
                          plot_bgcolor='rgba(0,0,0,0)', height=150,
                          margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True, key="kpi_kda")
    with k3:
        fig = go.Figure(go.Indicator(
            value=duration_mean,
            number={'font': {'size': 48, 'color': '#4ade80'}, 'suffix': ' мин'}
        ))
        fig.update_layout(title="Среднее время матча (мин)", paper_bgcolor='rgba(0,0,0,0)',
                          plot_bgcolor='rgba(0,0,0,0)', height=150,
                          margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True, key="kpi_dur")

    # Ряды графиков
    c1, c2 = st.columns(2)
    with c1:
        winrate_df = champion_group.copy()
        winrate_df['win_rate'] = winrate_df['sum'] / winrate_df['count'] * 100
        winrate_df = winrate_df[winrate_df['count'] >= 1]
        top_wr = winrate_df.nlargest(15, 'win_rate').sort_values('win_rate', ascending=True)
        fig = px.bar(top_wr, x='win_rate', y='champion', orientation='h',
                     title='Топ-15 чемпионов по винрейту',
                     labels={'win_rate': 'Винрейт (%)', 'champion': 'Чемпион'},
                     text='win_rate', color='win_rate', color_continuous_scale='Plasma')
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig.update_layout(xaxis_range=[0, 100], paper_bgcolor='rgba(0,0,0,0)',
                          plot_bgcolor='rgba(0,0,0,0)', font_color='#cbd5e1',
                          title_font_color='#e2e8f0',
                          yaxis=dict(gridcolor='#334155'), xaxis=dict(gridcolor='#334155'))
        st.plotly_chart(fig, use_container_width=True, key="tab1_wr")

    with c2:
        count_df = champion_group[champion_group['count'] >= 1]
        top_count = count_df.nlargest(15, 'count').sort_values('count', ascending=True)
        fig = px.bar(top_count, x='count', y='champion', orientation='h',
                     title='Топ-15 чемпионов по популярности',
                     labels={'count': 'Количество', 'champion': 'Чемпион'},
                     text='count', color='count', color_continuous_scale='Viridis')
        fig.update_traces(texttemplate='%{text:.0f}', textposition='outside')
        fig.update_layout(xaxis_range=[0, top_count['count'].max() * 1.15],
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#cbd5e1', title_font_color='#e2e8f0',
                          yaxis=dict(gridcolor='#334155'), xaxis=dict(gridcolor='#334155'))
        st.plotly_chart(fig, use_container_width=True, key="tab1_count")

    c1, c2 = st.columns(2)
    with c1:
        fig = px.histogram(chart_data, x='duration_min', nbins=30,
                           title='Длительность матчей',
                           labels={'duration_min': 'Длительность (мин)', 'count': 'Количество'},
                           color_discrete_sequence=['#636EFA'], marginal='box')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#cbd5e1', title_font_color='#e2e8f0',
                          yaxis=dict(gridcolor='#334155'), xaxis=dict(gridcolor='#334155'))
        st.plotly_chart(fig, use_container_width=True, key="tab1_hist_dur")

    with c2:
        fig = px.histogram(chart_data_players, x='league_points', nbins=30,
                           title='Распределение игроков по очкам лиги (LP)',
                           labels={'league_points': 'Количество LP', 'count': 'Количество'},
                           color_discrete_sequence=['#ab47bc'], marginal='box')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#cbd5e1', title_font_color='#e2e8f0',
                          yaxis=dict(gridcolor='#334155'), xaxis=dict(gridcolor='#334155'),
                          bargap=0.05)
        st.plotly_chart(fig, use_container_width=True, key="tab1_hist_lp")

# ═══ TAB 2 ═══
with tab2:
    grouped_mean = chart_data.groupby(['champion', 'team_position'], as_index=False).agg(
        avg_kills=('kills', 'mean'),
        avg_gold=('gold_earned', 'mean'),
        count=('match_id', 'size')
    )
    fig = px.scatter(grouped_mean, x='avg_kills', y='avg_gold', color='team_position',
                     size='count', hover_data=['champion'],
                     title='Связь убийств и золота по героям и ролям',
                     labels={'avg_kills': 'Средние убийства', 'avg_gold': 'Средний золотой доход'},
                     size_max=30, opacity=0.7, color_discrete_map=POS_COLORS)
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      font_color='#cbd5e1', title_font_color='#e2e8f0',
                      yaxis=dict(gridcolor='#334155'), xaxis=dict(gridcolor='#334155'))
    st.plotly_chart(fig, use_container_width=True, key="tab2_scatter")

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(top10, x='item_id', y='count', title='Топ-10 предметов у победивших',
                     color='count', color_continuous_scale='Teal')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#cbd5e1', title_font_color='#e2e8f0',
                          yaxis=dict(gridcolor='#334155'), xaxis=dict(gridcolor='#334155'))
        st.plotly_chart(fig, use_container_width=True, key="tab2_top10")

    with c2:
        fig = px.bar(role_top5, x='team_position', y='count', color='item_id',
                     title='Топ-5 предметов по ролям (победившие)',
                     color_discrete_sequence=px.colors.qualitative.Bold)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#cbd5e1', title_font_color='#e2e8f0',
                          yaxis=dict(gridcolor='#334155'), xaxis=dict(gridcolor='#334155'))
        st.plotly_chart(fig, use_container_width=True, key="tab2_role5")

# ═══ TAB 3 ═══
with tab3:
    c1, c2 = st.columns(2)
    with c1:
        box_data = []
        for pos in selected_positions:
            vals = chart_data[chart_data['team_position'] == pos]['kda'].clip(upper=15).values
            if len(vals) > 0:
                color = POS_COLORS.get(pos, '#888888')
                box_data.append(go.Box(
                    y=vals, name=pos, marker_color=color,
                    boxpoints=False, line=dict(width=1.5), fillcolor=color
                ))
        fig = go.Figure(data=box_data)
        fig.update_layout(title='Распределение KDA по ролям',
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#cbd5e1', title_font_color='#e2e8f0',
                          yaxis=dict(gridcolor='#334155', title='KDA', range=[0, 10]),
                          xaxis=dict(gridcolor='#334155'))
        st.plotly_chart(fig, use_container_width=True, key="tab3_box")

    with c2:
        corr_cols = ['kills', 'deaths', 'assists', 'gold_earned',
                     'damage_to_champions', 'minions_killed', 'vision_score', 'kda']
        corr = chart_data[corr_cols].corr().round(2)
        fig = go.Figure(data=[go.Heatmap(
            z=corr.values, x=corr.columns, y=corr.columns,
            colorscale='RdBu', zmid=0,
            text=corr.values, texttemplate='%{text}',
            textfont={'size': 10, 'color': '#e2e8f0'},
            hovertemplate='%{x} vs %{y}<br>r = %{z}<extra></extra>'
        )])
        fig.update_layout(title='Корреляционная матрица',
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font_color='#cbd5e1', title_font_color='#e2e8f0',
                          xaxis=dict(gridcolor='#334155', tickangle=-30),
                          yaxis=dict(gridcolor='#334155'))
        st.plotly_chart(fig, use_container_width=True, key="tab3_corr")

    table_df = chart_data.groupby('champion').agg(
        games=('match_id', 'count'),
        win_rate=('win_num', lambda x: round(x.mean() * 100, 1)),
        avg_kda=('kda', lambda x: round(x.mean(), 2)),
        avg_gold=('gold_earned', lambda x: round(x.mean())),
        avg_dmg=('damage_to_champions', lambda x: round(x.mean()))
    ).reset_index().sort_values('games', ascending=False).head(50)

    st.subheader("Статистика по чемпионам")
    st.dataframe(table_df, use_container_width=True, hide_index=True)