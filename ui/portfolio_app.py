from __future__ import annotations
import os
import pandas as pd
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from contextlib import suppress
from collections import defaultdict
from tkinter import messagebox, ttk
from pathlib import Path
import json
import threading
import time
import webbrowser
from ..ishares import universe
from ..ishares.fetch import IsharesSession
from ..ishares.parse import FundSheets
from ..portfolio.combined_holdings import calculate_combined_holdings
from .. import config

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# config.BRAVE_BROWSER_PATH  = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
# config.CHROMEDRIVER_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\chromedriver.exe"

# config.PROVIDER_PREFIXES = {
#     "ishares","vanguard","spdr","xtrackers","lyxor",
#     "invesco","ubs","amundi","wisdomtree",
# }
Path("data/raw").mkdir(parents=True, exist_ok=True)
ctk.set_appearance_mode("dark"); ctk.set_default_color_theme("green") 

class FundSelectorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ETF Portfolio Builder")
        self.geometry("1500x850")
        self.minsize(1300, 750)

        self.listbox_font = ctk.CTkFont(size=13)
        self.table_header_font = ctk.CTkFont(size=13, weight="bold")
        self.table_row_font = ctk.CTkFont(size=12)

        self.portfolio: list[pd.DataFrame] = [] 
        self.fund_data: pd.DataFrame = pd.DataFrame() 
        self.detailed_fund_data: dict[str, dict[str, pd.DataFrame]] = {} 
        self.last_data_pull_info: dict | None = None 
        self.display_map: dict[str, str] = {}
        self.full_to_disp: dict[str, str] = {}
        self.tkr2disp: dict[str, str] = {}
        self.disp2tkrs: defaultdict[str, list[str]] = defaultdict(list)
        self.all_disp_names: list[str] = []
        self.cur_trace_id: str | None = None
        self.dist_trace_id: str | None = None
        self.is_loading_data: bool = False 
        self.is_downloading_details: bool = False

        self.tab_view = ctk.CTkTabview(self, anchor="nw")
        self.tab_view.pack(expand=True, fill="both", padx=10, pady=10)

        self.portfolio_builder_tab = self.tab_view.add("Portfolio Builder")
        self.data_center_tab = self.tab_view.add("Data Center")
        self.dashboard_tab = self.tab_view.add("Portfolio Dashboard") 
        
        self.tab_view.set("Portfolio Builder") 

        self._create_portfolio_builder_ui(self.portfolio_builder_tab)
        self._create_data_center_ui(self.data_center_tab)
        self._create_dashboard_ui(self.dashboard_tab) 
        
        self.after(100, self.initial_load_fund_data)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _create_portfolio_builder_ui(self, tab_frame: ctk.CTkFrame):
        tab_frame.grid_columnconfigure(0, weight=10, uniform="cols_main_pb") 
        tab_frame.grid_columnconfigure(1, weight=3, uniform="cols_main_pb")  
        tab_frame.grid_columnconfigure(2, weight=10, uniform="cols_main_pb") 
        tab_frame.grid_rowconfigure(2, weight=1) 
        
        top_bar_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        top_bar_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(10,5), padx=20)
        top_bar_frame.grid_columnconfigure(0, weight=1)
        
        self.fund_universe_progress = ctk.CTkProgressBar(top_bar_frame, mode="determinate") 
        self.fund_universe_progress.grid(row=0, column=0, sticky="ew", padx=(0,10))
        self.fund_universe_progress.set(0)
        self.fund_universe_progress.grid_remove()
        
        self.update_btn = ctk.CTkButton(top_bar_frame, text="⬇  Update Fund List", width=170, command=self.refresh_universe)
        self.update_btn.grid(row=0, column=1)
        
        filter_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        filter_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 10), padx=20) 
        filter_frame.grid_columnconfigure(1, weight=1) 
        
        self.provider_var = tk.StringVar(value="All")
        self.provider_dd  = ctk.CTkOptionMenu(filter_frame, variable=self.provider_var, values=["All"], command=self._on_provider_change, width=180)
        self.provider_dd.grid(row=0, column=0, sticky="w", padx=(0,10))
        
        self.search_var  = tk.StringVar()
        self.search_entry = ctk.CTkEntry(filter_frame, textvariable=self.search_var, placeholder_text="Search fund name or ticker …")
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self.update_fund_list_display)
        
        left_panel = ctk.CTkFrame(tab_frame)
        left_panel.grid(row=2, column=0, sticky="nsew", padx=(20,5), pady=(0,20))
        left_panel.grid_rowconfigure(0, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)
        
        self.fund_listbox = tk.Listbox(left_panel, exportselection=False, font=self.listbox_font, borderwidth=0, highlightthickness=0, relief="flat")
        self.fund_listbox.grid(row=0, column=0, sticky="nsew")
        lb_scroll = ctk.CTkScrollbar(left_panel, command=self.fund_listbox.yview)
        lb_scroll.grid(row=0, column=1, sticky="ns")
        self.fund_listbox.configure(yscrollcommand=lb_scroll.set)
        self.fund_listbox.bind("<<ListboxSelect>>", self.on_fund_select)
        
        middle_panel = ctk.CTkFrame(tab_frame)
        middle_panel.grid(row=2, column=1, sticky="ns", padx=5, pady=(0,20))
        options_label = ctk.CTkLabel(middle_panel, text="Fund Options", font=ctk.CTkFont(weight="bold", size=14))
        options_label.pack(pady=(10,15), padx=10)
        self.currency_var = tk.StringVar()
        self.currency_dd = ctk.CTkOptionMenu(middle_panel, width=180, variable=self.currency_var, state="disabled", values=["-"])
        self.currency_dd.pack(pady=(0,10), padx=10, fill="x")
        self.dist_var = tk.StringVar()
        self.dist_dd = ctk.CTkOptionMenu(middle_panel, width=180, variable=self.dist_var, state="disabled", values=["-"])
        self.dist_dd.pack(pady=(0,10), padx=10, fill="x")
        self.mode_var = tk.StringVar(value="percent")
        self.mode_seg = ctk.CTkSegmentedButton(middle_panel, variable=self.mode_var, values=["percent","shares"])
        self.mode_seg.pack(pady=(0,15), padx=10, fill="x")
        self.add_btn = ctk.CTkButton(middle_panel, text="Add to Portfolio", command=self.add_to_portfolio, state="disabled")
        self.add_btn.pack(pady=(0,10), padx=10, fill="x")
        
        right_panel = ctk.CTkFrame(tab_frame)
        right_panel.grid(row=2, column=2, sticky="nsew", padx=(5,20), pady=(0,20))
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        self.port_lb = tk.Listbox(right_panel, exportselection=False, font=self.listbox_font, borderwidth=0, highlightthickness=0, relief="flat")
        self.port_lb.grid(row=0, column=0, sticky="nsew")
        pf_scroll = ctk.CTkScrollbar(right_panel, command=self.port_lb.yview)
        pf_scroll.grid(row=0, column=1, sticky="ns")
        self.port_lb.configure(yscrollcommand=pf_scroll.set)
        portfolio_buttons_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        portfolio_buttons_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10,0))
        portfolio_buttons_frame.grid_columnconfigure((0,1,2), weight=1) 
        self.load_btn = ctk.CTkButton(portfolio_buttons_frame, text="Load Portfolio", command=self.load_portfolio)
        self.load_btn.grid(row=0, column=0, padx=(0,3), sticky="ew")
        self.save_btn = ctk.CTkButton(portfolio_buttons_frame, text="Save Portfolio", command=self.save_portfolio)
        self.save_btn.grid(row=0, column=1, padx=3, sticky="ew")
        self.remove_btn = ctk.CTkButton(portfolio_buttons_frame, text="Remove Selected", command=self.remove_selected)
        self.remove_btn.grid(row=0, column=2, padx=(3,0), sticky="ew")

    def _create_data_center_ui(self, tab_frame: ctk.CTkFrame):
        tab_frame.grid_columnconfigure(0, weight=1)
        tab_frame.grid_rowconfigure(1, weight=1) 
        control_frame = ctk.CTkFrame(tab_frame)
        control_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        control_frame.grid_columnconfigure(0, weight=1) 
        self.detailed_data_progress = ctk.CTkProgressBar(control_frame, mode="determinate")
        self.detailed_data_progress.grid(row=0, column=0, sticky="ew", padx=(0,10), pady=5)
        self.detailed_data_progress.set(0)
        self.detailed_data_progress.grid_remove() 
        buttons_subframe = ctk.CTkFrame(control_frame, fg_color="transparent")
        buttons_subframe.grid(row=0, column=1, sticky="e", pady=5)
        self.download_details_btn = ctk.CTkButton(buttons_subframe, text="Download Portfolio Fund Data", command=self.trigger_detailed_data_download)
        self.download_details_btn.pack(side=tk.LEFT, padx=(0,5))
        self.save_details_btn = ctk.CTkButton(buttons_subframe, text="Save Downloaded Data", command=self.save_detailed_fund_data, state="disabled")
        self.save_details_btn.pack(side=tk.LEFT, padx=5)
        self.load_details_btn = ctk.CTkButton(buttons_subframe, text="Load Downloaded Data", command=self.load_detailed_fund_data)
        self.load_details_btn.pack(side=tk.LEFT, padx=(5,0))
        info_frame = ctk.CTkFrame(tab_frame)
        info_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0,10))
        info_frame.grid_columnconfigure(0, weight=1)
        info_frame.grid_rowconfigure(0, weight=1) 
        self.last_data_pull_label = ctk.CTkLabel(info_frame, text="Last Detailed Data Pull: N/A", anchor="w")
        self.last_data_pull_label.pack(pady=5, padx=10, fill="x")
        self.data_display_textbox = ctk.CTkTextbox(info_frame, state="disabled", wrap="word")
        self.data_display_textbox.pack(expand=True, fill="both", padx=10, pady=(0,10))
        self._update_data_display_textbox() 

    def _create_dashboard_ui(self, tab_frame: ctk.CTkFrame):
        scrollable_dashboard_frame = ctk.CTkScrollableFrame(tab_frame, fg_color="transparent")
        scrollable_dashboard_frame.pack(expand=True, fill="both")
        scrollable_dashboard_frame.grid_columnconfigure(0, weight=1)
        top_holdings_frame = ctk.CTkFrame(scrollable_dashboard_frame)
        top_holdings_frame.grid(row=0, column=0, sticky="new", padx=10, pady=10)
        top_holdings_frame.grid_columnconfigure(0, weight=1) 
        ctk.CTkLabel(top_holdings_frame, text="Top Consolidated Holdings", font=ctk.CTkFont(weight="bold", size=16)).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,5))
        holdings_cols = ("ticker", "name", "sector", "weight")
        self.top_holdings_treeview = ttk.Treeview(top_holdings_frame, columns=holdings_cols, show="headings", height=10) 
        self.top_holdings_treeview.heading("ticker", text="Ticker")
        self.top_holdings_treeview.heading("name", text="Name")
        self.top_holdings_treeview.heading("sector", text="Sector")
        self.top_holdings_treeview.heading("weight", text="Weight (%)")
        self.top_holdings_treeview.column("ticker", width=120, anchor=tk.W, stretch=tk.NO) 
        self.top_holdings_treeview.column("name", width=350, anchor=tk.W, stretch=tk.YES) 
        self.top_holdings_treeview.column("sector", width=200, anchor=tk.W, stretch=tk.NO)
        self.top_holdings_treeview.column("weight", width=100, anchor=tk.E, stretch=tk.NO) 
        self.top_holdings_treeview.grid(row=1, column=0, sticky="nsew", pady=(0,5))
        holdings_scrollbar = ctk.CTkScrollbar(top_holdings_frame, command=self.top_holdings_treeview.yview)
        holdings_scrollbar.grid(row=1, column=1, sticky="ns", pady=(0,5))
        self.top_holdings_treeview.configure(yscrollcommand=holdings_scrollbar.set)
        style = ttk.Style()
        bg_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        text_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        selected_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["fg_color"])
        style.theme_use("default")
        style.configure("Treeview", background=bg_color, foreground=text_color, fieldbackground=bg_color, borderwidth=0, font=self.table_row_font) 
        style.map("Treeview", background=[('selected', selected_color)], foreground=[('selected', text_color)])
        style.configure("Treeview.Heading", background=self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["border_color"]), foreground=text_color, relief="flat", font=self.table_header_font, padding=(5,5)) 
        style.map("Treeview.Heading", background=[('active', self._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["hover_color"]))])
        self.refresh_dashboard_btn = ctk.CTkButton(top_holdings_frame, text="Refresh Dashboard Data", command=self._update_dashboard_displays)
        self.refresh_dashboard_btn.grid(row=2, column=0, columnspan=2, sticky="w", pady=10)
        pie_chart_frame = ctk.CTkFrame(scrollable_dashboard_frame)
        pie_chart_frame.grid(row=1, column=0, sticky="new", padx=10, pady=10)
        ctk.CTkLabel(pie_chart_frame, text="Portfolio Allocation", font=ctk.CTkFont(weight="bold", size=16)).pack(anchor="w", pady=(0,5))
        self.allocation_chart_btn = ctk.CTkButton(pie_chart_frame, text="Show Allocation Chart (External)", command=self._generate_allocation_chart)
        self.allocation_chart_btn.pack(pady=5, anchor="w")
        self._update_top_holdings_display() 

    def _apply_appearance_mode(self, color_tuple_or_str):
        if isinstance(color_tuple_or_str, (list, tuple)): 
            return color_tuple_or_str[1] if ctk.get_appearance_mode() == "Dark" else color_tuple_or_str[0]
        return color_tuple_or_str 

    def _update_dashboard_displays(self): 
        print("Refreshing dashboard displays...")
        self._update_top_holdings_display()

    def _update_top_holdings_display(self):
        for item in self.top_holdings_treeview.get_children():
            self.top_holdings_treeview.delete(item)

        if not self.portfolio:
            self.top_holdings_treeview.insert("", tk.END, values=("Portfolio is empty.", "", "", ""))
            return
        if not self.detailed_fund_data:
            self.top_holdings_treeview.insert("", tk.END, values=("Detailed fund data not loaded.", "", "", ""))
            return
            
        try:
            active_portfolio_df = pd.concat(self.portfolio, ignore_index=True)
            valid_tickers = [p_df.iloc[0]['ticker'] for p_df in self.portfolio 
                             if p_df.iloc[0]['ticker'] in self.detailed_fund_data and 
                                self.detailed_fund_data[p_df.iloc[0]['ticker']].get("holdings") is not None and
                                not self.detailed_fund_data[p_df.iloc[0]['ticker']]["holdings"].empty]
            if not valid_tickers:
                self.top_holdings_treeview.insert("", tk.END, values=("No detailed holdings for portfolio funds.", "", "", ""))
                return

            filtered_portfolio_list = [p_df for p_df in self.portfolio if p_df.iloc[0]['ticker'] in valid_tickers]
            if not filtered_portfolio_list:
                 self.top_holdings_treeview.insert("", tk.END, values=("No valid funds for holdings calculation.", "", "", ""))
                 return
            
            active_portfolio_df_filtered = pd.concat(filtered_portfolio_list, ignore_index=True)
            relevant_detailed_data = { t: data for t, data in self.detailed_fund_data.items() if t in active_portfolio_df_filtered['ticker'].unique() }
            
            combined_df = calculate_combined_holdings(active_portfolio_df_filtered, relevant_detailed_data) 

            if combined_df.empty:
                self.top_holdings_treeview.insert("", tk.END, values=("No combined holdings data.", "", "", ""))
            else:
                weight_col_name = "Consolidated Weight" if "Consolidated Weight" in combined_df.columns else "Weight" 
                if weight_col_name not in combined_df.columns: 
                    self.top_holdings_treeview.insert("", tk.END, values=(f"Weight col '{weight_col_name}' missing.", "", "", ""))
                    print(f"Debug: combined_df columns are {combined_df.columns}")
                    return

                # Show top N holdings based on config
                top_N_holdings = combined_df.nlargest(config.TOP_N_HOLDINGS, weight_col_name)
                
                for _, row in top_N_holdings.iterrows():
                    ticker = str(row.get('Issuer Ticker', 'N/A'))
                    name = str(row.get('Name', 'N/A'))
                    sector = str(row.get('Sector', 'N/A'))
                    weight_val = row.get(weight_col_name, 0.0)
                    # Format weight as percentage string for display
                    weight_str = f"{weight_val:.2f}" if pd.notna(weight_val) else "N/A"
                    self.top_holdings_treeview.insert("", tk.END, values=(ticker, name, sector, weight_str))
        
        except Exception as e:
            print(f"Error updating top holdings display: {e}")
            error_message = f"Error: {str(e)}"
            self.top_holdings_treeview.insert("", tk.END, values=(error_message[:50], "See console for details", "", ""))


    def _generate_allocation_chart(self):
        if not self.portfolio: 
            messagebox.showwarning("Empty Portfolio", "Cannot generate chart for empty portfolio.", parent=self)
            return
        try:
            portfolio_df = pd.concat(self.portfolio, ignore_index=True)
            names, values, chart_title = None, None, ""
            if "weight" in portfolio_df.columns and portfolio_df["weight"].notna().any():
                names = portfolio_df["ticker"]
                values = portfolio_df["weight"]
                chart_title = "Portfolio Allocation by Weight (%)"
            elif "shares" in portfolio_df.columns and self.detailed_fund_data:
                market_values, names_for_shares = [], []
                for _, row in portfolio_df.iterrows():
                    ticker, shares = row["ticker"], row["shares"]
                    if ticker in self.detailed_fund_data and \
                       self.detailed_fund_data[ticker].get("historical") is not None and \
                       not self.detailed_fund_data[ticker]["historical"].empty:
                        latest_nav = self.detailed_fund_data[ticker]["historical"]["NAV"].iloc[-1]
                        market_values.append(latest_nav * shares)
                        names_for_shares.append(ticker)
                    else: 
                        market_values.append(0) 
                        names_for_shares.append(ticker)
                if sum(market_values) == 0: 
                    messagebox.showwarning("Chart Error", "Market values are zero or NAV missing.", parent=self)
                    return
                values = pd.Series(market_values)
                names = pd.Series(names_for_shares)
                chart_title = "Portfolio Allocation by Market Value"
            else: 
                messagebox.showwarning("Chart Error", "Insufficient data for allocation chart.", parent=self)
                return
            
            import plotly.graph_objects as go # Import here to avoid error if not installed globally

            fig = go.Figure(data=[go.Pie(labels=names, values=values, hole=.3, textinfo='label+percent')])
            fig.update_layout(title_text=chart_title, annotations=[dict(text='Funds', x=0.5, y=0.5, font_size=20, showarrow=False)])
            chart_path = Path("data/temp_allocation_chart.html")
            chart_path.parent.mkdir(parents=True, exist_ok=True) 
            fig.write_html(str(chart_path))
            webbrowser.open(chart_path.resolve().as_uri())
            messagebox.showinfo("Chart Generated", f"Chart opened in browser.\nFile: {chart_path}", parent=self)
        except ImportError: 
            messagebox.showerror("Plotly Missing", "'plotly' library required. Please install it.", parent=self)
        except Exception as e: 
            messagebox.showerror("Chart Error", f"Could not generate chart: {e}", parent=self)

    def _update_data_display_textbox(self):
        self.data_display_textbox.configure(state="normal")
        self.data_display_textbox.delete("1.0", tk.END)
        if not self.detailed_fund_data: 
            self.data_display_textbox.insert("1.0", "No detailed fund data loaded.")
        else:
            summary = f"Detailed data for {len(self.detailed_fund_data)} fund(s):\n\n"
            for ticker, data_dict in self.detailed_fund_data.items():
                summary += f"- {ticker}:\n"
                holdings_data = data_dict.get("holdings")
                historical_data = data_dict.get("historical")
                summary += f"  Holdings: {len(holdings_data) if holdings_data is not None else 0} records\n"
                summary += f"  Historical: {len(historical_data) if historical_data is not None else 0} records"
                if historical_data is not None and not historical_data.empty and isinstance(historical_data.index, pd.DatetimeIndex): 
                    summary += f", from {historical_data.index.min().strftime('%Y-%m-%d')} to {historical_data.index.max().strftime('%Y-%m-%d')}\n"
                else: 
                    summary += "\n"
                summary += "\n"
            self.data_display_textbox.insert("1.0", summary)
        if self.last_data_pull_info: 
            pull_date = self.last_data_pull_info.get("date", "Unknown")
            pulled_tickers = ", ".join(self.last_data_pull_info.get("tickers", []))
            self.last_data_pull_label.configure(text=f"Last Pull: {pull_date} (Tickers: {pulled_tickers or 'None'})")
        else: 
            self.last_data_pull_label.configure(text="Last Detailed Data Pull: N/A")
        self.data_display_textbox.configure(state="disabled")
        self.save_details_btn.configure(state="normal" if self.detailed_fund_data else "disabled")

    def _hide_and_reset_progress(self, pw: ctk.CTkProgressBar): 
        if pw.winfo_ismapped(): 
            pw.grid_remove()
        pw.set(0)

    def initial_load_fund_data(self):
        if self.is_loading_data: 
            return 
        self.is_loading_data = True
        self.update_btn.configure(state="disabled")
        self.fund_universe_progress.configure(mode="indeterminate")
        self.fund_universe_progress.set(0) 
        self.fund_universe_progress.grid()
        self.fund_universe_progress.start() 
        
        def on_load_progress(val_df):
            if not self.is_loading_data and not isinstance(val_df, pd.DataFrame): 
                return
            if isinstance(val_df, float):
                if self.fund_universe_progress.winfo_ismapped():
                    if self.fund_universe_progress.cget("mode") == "indeterminate": 
                        self.fund_universe_progress.stop()
                        self.fund_universe_progress.configure(mode="determinate")
                    self.fund_universe_progress.set(min(val_df, 0.99)) 
            elif isinstance(val_df, pd.DataFrame):
                self.fund_data = val_df
                self.is_loading_data = False 
                if self.fund_universe_progress.winfo_ismapped(): 
                    self.fund_universe_progress.stop()
                    self.fund_universe_progress.configure(mode="determinate")
                    self.fund_universe_progress.set(1.0)
                self._post_load_processing()
                self.update_btn.configure(state="normal")
                self.after(100, lambda: self._hide_and_reset_progress(self.fund_universe_progress))
            elif val_df is None: 
                pass
        try:
            poll_fn = universe.load_or_scrape(False, on_load_progress, config.BRAVE_BROWSER_PATH, config.CHROMEDRIVER_PATH)
            if callable(poll_fn): 
                self.poll_data_load(poll_fn, on_load_progress, self.fund_universe_progress) 
            elif isinstance(poll_fn, pd.DataFrame): 
                on_load_progress(poll_fn) 
            else: 
                self.is_loading_data = False
                self.update_btn.configure(state="normal")
                self._hide_and_reset_progress(self.fund_universe_progress)
        except Exception as exc: 
            messagebox.showerror("Load Failed", f"{exc}")
            self.fund_data=pd.DataFrame()
            self.is_loading_data=False
            self._post_load_processing()
            self._hide_and_reset_progress(self.fund_universe_progress)
            self.update_btn.configure(state="normal")

    def poll_data_load(self, poll_fn, on_prog_cb, prog_widget: ctk.CTkProgressBar): 
        loading_flag = self.is_loading_data if prog_widget == self.fund_universe_progress else self.is_downloading_details
        if not loading_flag: 
            if prog_widget.winfo_ismapped(): 
                prog_widget.stop() 
            self._hide_and_reset_progress(prog_widget)
            if prog_widget == self.fund_universe_progress: 
                self.update_btn.configure(state="normal")
            elif prog_widget == self.detailed_data_progress: 
                self.download_details_btn.configure(state="normal")
            return
        poll_fn() 
        if loading_flag: 
            self.after(250, lambda: self.poll_data_load(poll_fn, on_prog_cb, prog_widget))

    def refresh_universe(self):
        if self.is_loading_data: 
            return 
        self.is_loading_data = True
        self.update_btn.configure(state="disabled")
        self.fund_universe_progress.configure(mode="indeterminate")
        self.fund_universe_progress.set(0)
        self.fund_universe_progress.grid()
        self.fund_universe_progress.start()
        def on_refresh_prog(val_df):
            if not self.is_loading_data and not isinstance(val_df, pd.DataFrame): 
                return
            if isinstance(val_df, float):
                if self.fund_universe_progress.winfo_ismapped():
                    if self.fund_universe_progress.cget("mode") == "indeterminate": 
                        self.fund_universe_progress.stop()
                        self.fund_universe_progress.configure(mode="determinate")
                    self.fund_universe_progress.set(min(val_df, 0.99))
            elif isinstance(val_df, pd.DataFrame):
                self.fund_data = val_df
                self.is_loading_data = False
                if self.fund_universe_progress.winfo_ismapped(): 
                    self.fund_universe_progress.stop()
                    self.fund_universe_progress.configure(mode="determinate")
                    self.fund_universe_progress.set(1.0)
                self._post_load_processing()
                self.update_btn.configure(state="normal")
                self.after(100, lambda: self._hide_and_reset_progress(self.fund_universe_progress))
            elif val_df is None: 
                pass
        try:
            poll_fn = universe.load_or_scrape(True, on_refresh_prog, config.BRAVE_BROWSER_PATH, config.CHROMEDRIVER_PATH)
            if callable(poll_fn): 
                self.poll_data_load(poll_fn, on_refresh_prog, self.fund_universe_progress)
            elif isinstance(poll_fn, pd.DataFrame): 
                on_refresh_prog(poll_fn)
            else: 
                self.is_loading_data = False
                self.update_btn.configure(state="normal")
                self._hide_and_reset_progress(self.fund_universe_progress)
        except Exception as exc: 
            messagebox.showerror("Refresh Failed", f"{exc}")
            self.is_loading_data=False
            self._hide_and_reset_progress(self.fund_universe_progress)
            self.update_btn.configure(state="normal")

    def _post_load_processing(self):
        df = self.fund_data
        if df.empty or not all(col in df.columns for col in ["name", "ticker", "link"]): 
            print("Fund data incomplete.")
            self.display_map, self.full_to_disp, self.tkr2disp, self.disp2tkrs, self.all_disp_names = {}, {}, {}, defaultdict(list), []
            self.provider_dd.configure(values=["N/A"])
            self.provider_var.set("N/A")
            self._update_fund_listbox_display([])
            self._clear_fund_options()
            return
        df["provider"] = df["name"].astype(str).str.split().str[0].str.lower()
        self.display_map, self.full_to_disp = {}, {}
        for full_name in df["name"].dropna().unique(): 
            full_name_str = str(full_name)
            first_word, *rest = full_name_str.split(" ", 1)
            disp_name = rest[0] if first_word.lower() in config.PROVIDER_PREFIXES and rest else full_name_str
            self.display_map[disp_name] = full_name_str
            self.full_to_disp[full_name_str] = disp_name
        name_ticker_pairs = df[["name", "ticker"]].dropna(subset=["name", "ticker"])
        self.tkr2disp = {str(t).lower(): self.full_to_disp[n] for n, t in name_ticker_pairs.itertuples(index=False) if n in self.full_to_disp}
        self.disp2tkrs = defaultdict(list) 
        for t, d_name in self.tkr2disp.items(): 
            self.disp2tkrs[d_name].append(t)
        unique_providers = sorted([p for p in df["provider"].dropna().unique() if p]) 
        prov_opts = ["All"] + unique_providers
        self.provider_dd.configure(values=prov_opts if prov_opts != ["All"] else ["All", "N/A"]) 
        cur_prov = self.provider_var.get()
        if not cur_prov or cur_prov.lower() not in [opt.lower() for opt in prov_opts]: 
            self.provider_var.set("iShares" if "ishares" in unique_providers else (prov_opts[0] if prov_opts else "N/A"))
        self.all_disp_names = sorted(self.display_map.keys())
        self.update_fund_list_display() 
        if not self.fund_listbox.curselection(): 
            self._clear_fund_options()

    def _on_provider_change(self, sel_prov=None): 
        self.search_var.set("")
        self.update_fund_list_display()

    def _is_fund_visible_by_provider(self, disp_name: str) -> bool: 
        sel_prov = self.provider_var.get().lower()
        if sel_prov in ["all", "", "n/a"]: 
            return True
        full_name = self.display_map.get(disp_name)
        return bool(full_name and str(full_name).lower().startswith(sel_prov))

    def _update_fund_listbox_display(self, names_to_disp: list[str] | None = None):
        cur_sel_txt = self.fund_listbox.get(self.fund_listbox.curselection()) if self.fund_listbox.curselection() else None
        self.fund_listbox.delete(0, "end") 
        if names_to_disp is None: 
            query = self.search_var.get().lower().strip()
            candidates = [dn for dn in self.all_disp_names if self._is_fund_visible_by_provider(dn)]
            if not query: 
                names_to_disp = candidates
            else: 
                hits_name = {n for n in candidates if query in n.lower()}
                hits_ticker = {self.tkr2disp[t] for t in self.tkr2disp if query in t and self.tkr2disp[t] in candidates}
                names_to_disp = sorted(list(hits_name.union(hits_ticker)))
        for name in names_to_disp: 
            self.fund_listbox.insert("end", name)
        if cur_sel_txt and names_to_disp and cur_sel_txt in names_to_disp:
            try: 
                idx = names_to_disp.index(cur_sel_txt)
                self.fund_listbox.selection_set(idx)
                self.fund_listbox.see(idx)
                self.on_fund_select() 
            except ValueError: 
                self._clear_fund_options()
        elif not self.fund_listbox.curselection() and names_to_disp: 
            self._clear_fund_options() 
        elif not names_to_disp: 
            self._clear_fund_options()

    def update_fund_list_display(self, event=None): 
        self._update_fund_listbox_display() 

    def _clear_fund_options(self): 
        self._safe_remove_trace(self.cur_trace_id, self.currency_var)
        self._safe_remove_trace(self.dist_trace_id, self.dist_var)
        self.currency_var.set("")
        self.dist_var.set("")   
        self.currency_dd.configure(values=["-"], state="disabled")
        self.currency_dd.set("-") 
        self.dist_dd.configure(values=["-"], state="disabled")
        self.dist_dd.set("-")   
        self.add_btn.configure(state="disabled")

    def on_fund_select(self, event=None): 
        sel_idx = self.fund_listbox.curselection()
        if not sel_idx: 
            self._clear_fund_options()
            return
        try: 
            sel_disp_name = self.fund_listbox.get(sel_idx[0])
            full_fund_name = self.display_map.get(sel_disp_name) 
            if not full_fund_name or self.fund_data.empty: 
                self._clear_fund_options()
                return
        except (tk.TclError, KeyError): 
            self._clear_fund_options()
            return
        fund_rows = self.fund_data[self.fund_data["name"] == full_fund_name]
        if fund_rows.empty: 
            self._clear_fund_options()
            return
        self.add_btn.configure(state="normal")
        self._set_currency_dropdown(fund_rows)
        self._on_currency_changed(fund_rows) 

    def _set_currency_dropdown(self, fund_rows: pd.DataFrame): 
        self._safe_remove_trace(self.cur_trace_id, self.currency_var) 
        opts = (fund_rows["currency"].astype(str) + " – " + fund_rows["hedging"].astype(str)).unique().tolist() if "currency" in fund_rows.columns and "hedging" in fund_rows.columns else []
        opts = sorted([o for o in opts if o and o.lower().replace(" ", "") != "nan–nan"]) 
        if opts: 
            self.currency_dd.configure(values=opts, state="normal")
            self.currency_var.set(opts[0]) 
        else: 
            self.currency_var.set("")
            self.currency_dd.configure(values=["-"], state="disabled")
            self.currency_dd.set("-") 
        self.cur_trace_id = self.currency_var.trace_add("write", lambda *_: self._on_currency_changed(fund_rows))

    def _set_distribution_dropdown(self, cur_filt_rows: pd.DataFrame): 
        self._safe_remove_trace(self.dist_trace_id, self.dist_var) 
        opts = sorted(cur_filt_rows["distribution"].astype(str).dropna().unique().tolist()) if "distribution" in cur_filt_rows.columns else []
        opts = [o for o in opts if o and o.lower() != "nan"] 
        if opts: 
            self.dist_dd.configure(values=opts, state="normal")
            cur_dist = self.dist_var.get()
            self.dist_var.set(cur_dist if cur_dist in opts else opts[0]) 
        else: 
            self.dist_var.set("")
            self.dist_dd.configure(values=["-"], state="disabled")
            self.dist_dd.set("-") 
        
    def _on_currency_changed(self, all_rows_fund: pd.DataFrame): 
        sel_cur_hed = self.currency_var.get()
        empty_df_cols = all_rows_fund.columns if not all_rows_fund.empty else ['distribution']
        if not sel_cur_hed or " – " not in sel_cur_hed: 
            self._set_distribution_dropdown(pd.DataFrame(columns=empty_df_cols))
            return
        try: 
            cur, hed = sel_cur_hed.split(" – ", 1)
        except ValueError: 
            self._set_distribution_dropdown(pd.DataFrame(columns=empty_df_cols))
            return
        mask = (all_rows_fund["currency"].astype(str) == cur) & (all_rows_fund["hedging"].astype(str) == hed)
        self._set_distribution_dropdown(all_rows_fund[mask])
        
    def add_to_portfolio(self): 
        sel_idx = self.fund_listbox.curselection()
        if not sel_idx: 
            messagebox.showwarning("Selection Error", "Select a fund.")
            return
        sel_disp_name = self.fund_listbox.get(sel_idx[0])
        full_fund_name = self.display_map.get(sel_disp_name)
        if not full_fund_name: 
            messagebox.showerror("Data Error", "Fund details not found.")
            return
        sel_cur_hed = self.currency_var.get()
        sel_dist = self.dist_var.get()
        if not sel_cur_hed or " – " not in sel_cur_hed or not sel_dist or sel_dist == "-": 
            messagebox.showwarning("Selection Error", "Select currency, hedging, distribution.")
            return
        try: 
            cur, hed = sel_cur_hed.split(" – ", 1)
        except ValueError: 
            messagebox.showerror("Input Error", "Invalid currency/hedging.")
            return
        
        mask = ( (self.fund_data["name"] == full_fund_name) & 
                 (self.fund_data["currency"].astype(str) == cur) & 
                 (self.fund_data["hedging"].astype(str) == hed) & 
                 (self.fund_data["distribution"].astype(str) == sel_dist) )
        fund_var_row = self.fund_data[mask]
        if fund_var_row.empty: 
            messagebox.showerror("Data Error", "Selected fund variant not in universe.")
            return
        
        mode = self.mode_var.get()
        dlg_txt = "Weight (% >0-100):" if mode == "percent" else "Shares (>0):"
        dlg = ctk.CTkInputDialog(title="Add Position", text=dlg_txt)
        input_val = dlg.get_input()
        if input_val is None: 
            return 
        try: 
            val = float(input_val)
            if val <= 0: 
                raise ValueError("Positive value required.")
            if mode == "percent" and not (0 < val <= 100): 
                raise ValueError("Percent: 0 < val <= 100.")
        except ValueError as e: 
            messagebox.showerror("Invalid Input", f"{e}")
            return

        record = fund_var_row.iloc[[0]].copy()
        ticker = record["ticker"].iloc[0]
        lbl_parts = [str(ticker), f"{cur}-{hed}", sel_dist]
        if mode == "percent": 
            record["weight"] = val
            lbl_parts.append(f"{val:.2f}%")
        else: 
            record["shares"] = val
            lbl_parts.append(f"{val:g} sh") 
        
        self.portfolio.append(record)
        self.port_lb.insert("end", " | ".join(lbl_parts))
        if len(self.portfolio) == 1: 
            self.mode_seg.configure(state="disabled")

    def remove_selected(self): 
        sel_idx = self.port_lb.curselection()
        if not sel_idx: 
            messagebox.showwarning("Selection Error", "Select item to remove.")
            return
        try: 
            self.port_lb.delete(sel_idx[0])
            self.portfolio.pop(sel_idx[0]) 
        except Exception as e: 
            messagebox.showerror("Error", f"Could not remove: {e}")
        if not self.portfolio: 
            self.mode_seg.configure(state="normal") 

    def save_portfolio(self): 
        if not self.portfolio: 
            messagebox.showwarning("Empty Portfolio", "Nothing to save.")
            return
        name_dlg = ctk.CTkInputDialog(title="Save Portfolio", text="Enter portfolio name:")
        pf_name = name_dlg.get_input()
        if not pf_name: 
            messagebox.showinfo("Save Cancelled", "Cancelled.")
            return
        safe_name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in pf_name).rstrip()
        def_fn = f"portfolio_{safe_name if safe_name else 'untitled'}.csv"
        try:
            fp = filedialog.asksaveasfilename(initialfile=def_fn, defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
            if not fp: 
                return
            full_df = pd.concat(self.portfolio, ignore_index=True)
            cols = ["name", "ticker", "currency", "hedging", "distribution", "link", "provider", "weight", "shares"]
            exist_cols = [c for c in cols if c in full_df.columns]
            if not exist_cols: 
                messagebox.showerror("Save Error", "No columns to save.")
                return
            full_df[exist_cols].to_csv(fp, index=False)
            messagebox.showinfo("Saved", f"Portfolio '{pf_name}' saved to:\n{fp}")
        except Exception as e: 
            messagebox.showerror("Save Error", f"Failed to save: {str(e)}")

    def load_portfolio(self): 
        fp = filedialog.askopenfilename(title="Load Portfolio", defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not fp: 
            return
        try:
            ld_df = pd.read_csv(fp)
            req_cols = ["name", "ticker", "currency", "hedging", "distribution", "link"] 
            has_amt = "weight" in ld_df.columns or "shares" in ld_df.columns
            miss_cols = [c for c in req_cols if c not in ld_df.columns]
            if miss_cols or not has_amt: 
                messagebox.showerror("Load Error", f"File missing: {', '.join(miss_cols) if miss_cols else 'weight/shares'}.")
                return
            self.portfolio.clear()
            self.port_lb.delete(0, tk.END)
            for _, row in ld_df.iterrows():
                item_data = {c: [row[c]] for c in ld_df.columns if c in row and pd.notna(row[c])}
                item_df = pd.DataFrame(item_data)
                self.portfolio.append(item_df)
                tkr = str(row.get("ticker", "N/A"))
                cur = str(row.get("currency", "N/A"))
                hed = str(row.get("hedging", ""))
                dist = str(row.get("distribution", "N/A"))
                lbl_parts = [tkr, f"{cur}{' – ' + hed if hed and hed.lower() != 'none' else ''}", dist]
                if "weight" in row and pd.notna(row["weight"]): 
                    lbl_parts.append(f"{float(row['weight']):.2f}%")
                elif "shares" in row and pd.notna(row["shares"]): 
                    lbl_parts.append(f"{float(row['shares']):g} sh")
                self.port_lb.insert("end", " | ".join(lbl_parts))
            self.mode_seg.configure(state="disabled" if self.portfolio else "normal")
            messagebox.showinfo("Loaded", f"Portfolio loaded from:\n{fp}")
        except Exception as e: 
            messagebox.showerror("Load Error", f"Failed to load: {str(e)}")

    def trigger_detailed_data_download(self):
        if not self.portfolio: 
            messagebox.showwarning("Empty Portfolio", "Add funds first.")
            return
        if self.is_downloading_details: 
            messagebox.showwarning("In Progress", "Download in progress.")
            return
        self.is_downloading_details = True
        self.download_details_btn.configure(state="disabled")
        self.detailed_data_progress.configure(mode="determinate")
        self.detailed_data_progress.set(0)
        self.detailed_data_progress.grid()
        threading.Thread(target=self._perform_detailed_data_download, daemon=True).start()

    def _perform_detailed_data_download(self):
        print("Starting detailed data download...")
        dld_tickers = []
        Path("data/raw").mkdir(parents=True, exist_ok=True) 
        try:
            SessCls, SheetsCls = IsharesSession, FundSheets
            with SessCls(chrome_binary=config.BRAVE_BROWSER_PATH, chromedriver_path=config.CHROMEDRIVER_PATH) as sess:
                num_funds = len(self.portfolio)
                if num_funds == 0: 
                    print("Portfolio empty.")
                    self.after(0, lambda: messagebox.showinfo("No Funds","Portfolio empty"))
                    return
                for i, fund_rec_df in enumerate(self.portfolio):
                    if not self.is_downloading_details: 
                        print("Download cancelled.")
                        break 
                    if fund_rec_df.empty: 
                        continue
                    fund_rec = fund_rec_df.iloc[0]
                    fund_link = fund_rec.get("link")
                    fund_tkr = fund_rec.get("ticker", f"unk_{i}")
                    if not fund_link or fund_link == "N/A" or not isinstance(fund_link, str) or not fund_link.startswith("http"): 
                        print(f"Skipping {fund_tkr}: Bad link ('{fund_link}').")
                        self.after(0, lambda p=(i+1)/num_funds, ft=fund_tkr: (self.detailed_data_progress.set(p) if self.detailed_data_progress.winfo_ismapped() else None, print(f"Prog skip {ft}: {p*100:.1f}%")))
                        continue
                    try:
                        print(f"Downloading: {fund_tkr} ({fund_link})")
                        xls_link = sess.xls_link_from_product_page(fund_link)
                        xls_path = sess.download_xls(xls_link, overwrite=True)
                        sheets = SheetsCls(xls_path)
                        hld = sheets.holdings.copy() if sheets.holdings is not None else pd.DataFrame()
                        hist = sheets.historical.copy() if sheets.historical is not None else pd.DataFrame()
                        distrib = sheets.distributions.copy() if sheets.distributions is not None else pd.DataFrame()
                        self.detailed_fund_data[fund_tkr] = {"holdings": hld, "historical": hist, "distributions": distrib, "source_xls": str(xls_path)}
                        dld_tickers.append(fund_tkr)
                        print(f"Processed: {fund_tkr}")
                    except Exception as e: 
                        print(f"Error for {fund_tkr} ({fund_link}): {e}")
                        self.after(0, lambda ft=fund_tkr, em=str(e): messagebox.showerror("Download Error", f"Error for {ft}:\n{em}"))
                    self.after(0, lambda p=(i+1)/num_funds, ft=fund_tkr: (self.detailed_data_progress.set(p) if self.detailed_data_progress.winfo_ismapped() else None, print(f"Prog for {ft}: {p*100:.1f}%")))
            if self.is_downloading_details : 
                self.last_data_pull_info = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "tickers": dld_tickers}
        except Exception as e: 
            print(f"Session error: {e}")
            self.after(0, lambda em=str(e): messagebox.showerror("Download Failed", f"Session error: {em}"))
        finally: 
            self.is_downloading_details = False
            self.after(0, self._finalize_detailed_download_ui)

    def _finalize_detailed_download_ui(self):
        if self.detailed_data_progress.winfo_ismapped(): 
            self.detailed_data_progress.stop()
            self.detailed_data_progress.set(1.0)
        self.after(500, lambda: self._hide_and_reset_progress(self.detailed_data_progress))
        self.download_details_btn.configure(state="normal")
        self._update_data_display_textbox() 

    def save_detailed_fund_data(self): 
        if not self.detailed_fund_data: 
            messagebox.showwarning("No Data", "No detailed data to save.", parent=self)
            return
        dir_path = filedialog.askdirectory(title="Select Directory to Save Detailed Fund Data")
        if not dir_path: 
            return
        save_dir = Path(dir_path)
        try:
            manifest = { "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"), "last_data_pull": self.last_data_pull_info, "tickers": list(self.detailed_fund_data.keys()) }
            with open(save_dir / "manifest.json", "w") as f: 
                json.dump(manifest, f, indent=4)
            for tkr, data in self.detailed_fund_data.items():
                if data.get("holdings") is not None and not data["holdings"].empty: 
                    data["holdings"].to_parquet(save_dir / f"{tkr}_holdings.parquet", index=False)
                if data.get("historical") is not None and not data["historical"].empty: 
                    df_h = data["historical"]
                    if isinstance(df_h.index, pd.DatetimeIndex) and df_h.index.name: 
                        df_h.reset_index().to_parquet(save_dir / f"{tkr}_historical.parquet", index=False)
                    else: 
                        df_h.to_parquet(save_dir / f"{tkr}_historical.parquet", index=isinstance(df_h.index, pd.MultiIndex))
                if data.get("distributions") is not None and not data["distributions"].empty: 
                    data["distributions"].to_parquet(save_dir / f"{tkr}_distributions.parquet", index=False)
            messagebox.showinfo("Data Saved", f"Detailed data saved to:\n{save_dir}", parent=self)
        except Exception as e: 
            messagebox.showerror("Save Error", f"Failed to save detailed data: {e}", parent=self)

    def load_detailed_fund_data(self): 
        dir_path = filedialog.askdirectory(title="Select Directory with Detailed Fund Data")
        if not dir_path: 
            return
        load_dir = Path(dir_path)
        manifest_p = load_dir / "manifest.json"
        if not manifest_p.exists(): 
            messagebox.showerror("Load Error", "manifest.json not found.", parent=self)
            return
        try:
            with open(manifest_p, "r") as f: 
                manifest = json.load(f)
            loaded_data = {}
            for tkr in manifest.get("tickers", []):
                loaded_data[tkr] = {}
                hld_p, hist_p, dist_p = load_dir/f"{tkr}_holdings.parquet", load_dir/f"{tkr}_historical.parquet", load_dir/f"{tkr}_distributions.parquet"
                loaded_data[tkr]["holdings"] = pd.read_parquet(hld_p) if hld_p.exists() else pd.DataFrame()
                if hist_p.exists(): 
                    hist_df = pd.read_parquet(hist_p) 
                    if "As Of" in hist_df.columns: 
                        hist_df["As Of"] = pd.to_datetime(hist_df["As Of"])
                        hist_df = hist_df.set_index("As Of")
                    loaded_data[tkr]["historical"] = hist_df
                else: 
                    loaded_data[tkr]["historical"] = pd.DataFrame()
                loaded_data[tkr]["distributions"] = pd.read_parquet(dist_p) if dist_p.exists() else pd.DataFrame()
            self.detailed_fund_data = loaded_data
            self.last_data_pull_info = manifest.get("last_data_pull") 
            self._update_data_display_textbox()
            messagebox.showinfo("Data Loaded", f"Detailed data loaded from:\n{load_dir}", parent=self)
        except Exception as e: 
            messagebox.showerror("Load Error", f"Failed to load detailed data: {e}", parent=self)

    def _safe_remove_trace(self, trace_id: str | None, var: tk.Variable):
        if trace_id:
            try: 
                var.trace_remove("write", trace_id)
            except tk.TclError: 
                pass 
            if var == self.currency_var: 
                self.cur_trace_id = None
            elif var == self.dist_var: 
                self.dist_trace_id = None

    def on_close(self): 
        self.quit()
        self.destroy()