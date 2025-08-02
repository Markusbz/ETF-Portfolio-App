import pandas as pd
import plotly.graph_objects as go
import webbrowser
from pathlib import Path

def plot_backtest_results(results_df: pd.DataFrame, title: str = "Portfolio Performance Backtest Comparison"):
    """
    Generates an interactive Plotly chart from backtest results and opens it in a browser.

    Args:
        results_df (pd.DataFrame): DataFrame with datetime index and columns for each 
                                   strategy's cumulative performance.
        title (str): The title for the chart.
    """
    fig = go.Figure()

    # Add a trace for each rebalancing strategy
    for col in results_df.columns:
        fig.add_trace(go.Scatter(
            x=results_df.index,
            y=results_df[col],
            mode='lines',
            name=col
        ))

    # --- Configure the plot layout for a professional, dark-themed look ---
    fig.update_layout(
        title_text=title,
        title_x=0.5, # Center the title
        xaxis_title="Date",
        yaxis_title="Cumulative Growth (Log Scale)",
        yaxis_type="log", # Use log scale for better visualization of long-term growth
        legend_title_text='Rebalancing Strategy',
        font=dict(
            family="Arial, sans-serif",
            size=12,
            color="white"
        ),
        template="plotly_dark", # Use a pre-built dark theme
        paper_bgcolor='rgba(0,0,0,0)', # Transparent background
        plot_bgcolor='#2B2B2B',
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='#444' # Darker grid lines
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='#444' # Darker grid lines
        )
    )

    # --- Save to a temporary HTML file and open in the default web browser ---
    chart_path = Path("data/temp_backtest_chart.html")
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(chart_path))
    
    print(f"Opening backtest chart at: {chart_path.resolve().as_uri()}")
    webbrowser.open(chart_path.resolve().as_uri())
