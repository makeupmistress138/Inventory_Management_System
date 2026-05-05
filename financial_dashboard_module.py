import customtkinter as ctk
from firebase_config import db
import threading

class FinancialDashboardModule(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.setup_ui()
        self.start_loading()

    def setup_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        nav_bar = ctk.CTkFrame(self, fg_color="transparent")
        nav_bar.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkButton(nav_bar, text="← Back to Menu", width=120, fg_color="#444", command=self.controller.show_main_menu).pack(side="left")
        
        self.refresh_btn = ctk.CTkButton(nav_bar, text="↻ Recalculate", width=120, fg_color="#1f538d", command=self.start_loading)
        self.refresh_btn.pack(side="right")
        
        ctk.CTkLabel(self, text="FINANCIAL DASHBOARD (All-Time)", font=("Arial", 28, "bold")).grid(row=0, column=0, pady=(60,0))

        self.card_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.card_frame.grid(row=1, column=0, sticky="nsew", padx=40, pady=20)
        self.card_frame.grid_columnconfigure((0,1,2), weight=1)

    def create_card(self, parent, title, amount, row, col, color="#3a7ebf"):
        f = ctk.CTkFrame(parent, fg_color="#2b2b2b", corner_radius=10)
        f.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(f, text=title, font=("Arial", 16, "bold"), text_color="gray").pack(pady=(20, 5))
        ctk.CTkLabel(f, text=f"{amount:,.2f} EGP", font=("Arial", 28, "bold"), text_color=color).pack(pady=(0, 20))

    def start_loading(self):
        self.refresh_btn.configure(state="disabled", text="Loading...")
        for w in self.card_frame.winfo_children(): w.destroy()
        
        self.loading_label = ctk.CTkLabel(self.card_frame, text="Fetching Data from Cloud...", font=("Arial", 20, "italic"), text_color="gray")
        self.loading_label.grid(row=0, column=1, pady=100)
        
        threading.Thread(target=self.fetch_and_calculate, daemon=True).start()

    def fetch_and_calculate(self):
        try:
            gross_revenue = 0.0
            sales_returns = 0.0
            cogs = 0.0
            
            delivery_losses = 0.0
            commission_losses = 0.0
            defective_shrinkage = 0.0
            
            total_deposits_held = 0.0
            forfeited_deposit_income = 0.0
            uncollected_cash = 0.0

            all_orders = db.collection("sales_orders").get()
            
            for o in all_orders:
                data = o.to_dict()
                status = data.get("status", "")
                
                if status == "CANCELLED": continue

                total_val = float(data.get("total_sale_value", 0))
                deposit = float(data.get("deposit_paid", 0))
                payout = float(data.get("payout_received", 0))
                
                # Deposits collected on ALL non-cancelled orders
                total_deposits_held += deposit

                # Active orders do not trigger revenue or COGS yet.
                if status == "ACTIVE":
                    continue

                # Once Shipped, Completed, or Returned, Gross Revenue is locked in.
                gross_revenue += total_val
                
                # Calculate the exact COGS of items currently with the customer
                initial_cogs = 0.0
                for item in data.get("items", []):
                    initial_cogs += float(item.get("landed_cost", 0)) * int(item.get("qty", 0))
                cogs += initial_cogs

                # Pre-Completion Returns (Courier failed)
                if status == "RETURNED" and "sales_return_value" in data:
                    sales_returns += float(data.get("sales_return_value", 0))
                    delivery_losses += float(data.get("delivery_loss", 0))
                    forfeited_deposit_income += deposit # Kept deposit as income

                # Post-Completion RMAs (Partial or Full)
                if "rma_refund" in data:
                    sales_returns += float(data.get("rma_refund", 0))

                # Capture shrinkage from damaged returns
                defective_shrinkage += float(data.get("defective_loss", 0))

                # Uncollected cash calculations
                if status == "SHIPPED":
                    uncollected_cash += (total_val - deposit)
                    
                # Commission Calculation
                elif status == "COMPLETED":
                    expected_payout = total_val - deposit
                    if payout < expected_payout:
                        commission_losses += (expected_payout - payout)

            net_revenue = gross_revenue - sales_returns
            gross_profit = net_revenue - cogs
            total_losses = delivery_losses + commission_losses + defective_shrinkage
            
            net_profit = gross_profit + forfeited_deposit_income - total_losses

            results = {
                "gross_revenue": gross_revenue,
                "sales_returns": sales_returns,
                "net_revenue": net_revenue,
                "cogs": cogs,
                "gross_profit": gross_profit,
                "total_deposits_held": total_deposits_held,
                "total_losses": total_losses,
                "uncollected_cash": uncollected_cash,
                "net_profit": net_profit
            }
            
            self.after(0, lambda: self.update_ui_with_results(results))
            
        except Exception as e:
            self.after(0, lambda: self.show_error(str(e)))

    def update_ui_with_results(self, results):
        for w in self.card_frame.winfo_children(): w.destroy()
        
        self.create_card(self.card_frame, "1. Gross Revenue", results["gross_revenue"], 0, 0)
        self.create_card(self.card_frame, "2. Sales Returns / RMAs", results["sales_returns"], 0, 1, color="#a32e2e")
        self.create_card(self.card_frame, "3. Net Revenue", results["net_revenue"], 0, 2)
        
        self.create_card(self.card_frame, "4. COGS (Cost of Goods)", results["cogs"], 1, 0, color="#c27b1f")
        self.create_card(self.card_frame, "5. Gross Profit", results["gross_profit"], 1, 1, color="#2e7d32")
        self.create_card(self.card_frame, "6. Total Deposits Held (Cash)", results["total_deposits_held"], 1, 2)
        
        self.create_card(self.card_frame, "7. Total Business Losses", results["total_losses"], 2, 0, color="#a32e2e")
        self.create_card(self.card_frame, "8. Uncollected Cash (Couriers)", results["uncollected_cash"], 2, 1, color="#8e24aa")
        self.create_card(self.card_frame, "9. NET PROFIT", results["net_profit"], 2, 2, color="green")
        
        self.refresh_btn.configure(state="normal", text="↻ Recalculate")

    def show_error(self, err_msg):
        for w in self.card_frame.winfo_children(): w.destroy()
        ctk.CTkLabel(self.card_frame, text=f"Error Loading Data:\n{err_msg}", text_color="red", font=("Arial", 16)).grid(row=0, column=1, pady=50)
        self.refresh_btn.configure(state="normal", text="↻ Recalculate")