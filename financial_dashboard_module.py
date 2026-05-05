import customtkinter as ctk
from firebase_config import db

class FinancialDashboardModule(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.setup_ui()
        self.calculate_financials()

    def setup_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        nav_bar = ctk.CTkFrame(self, fg_color="transparent")
        nav_bar.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        ctk.CTkButton(nav_bar, text="← Back to Menu", width=120, fg_color="#444", command=self.controller.show_main_menu).pack(side="left")
        ctk.CTkButton(nav_bar, text="↻ Recalculate", width=120, fg_color="#1f538d", command=self.calculate_financials).pack(side="right")
        
        ctk.CTkLabel(self, text="FINANCIAL DASHBOARD (All-Time)", font=("Arial", 28, "bold")).grid(row=0, column=0, pady=(60,0))

        self.card_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.card_frame.grid(row=1, column=0, sticky="nsew", padx=40, pady=20)
        self.card_frame.grid_columnconfigure((0,1,2), weight=1)

    def create_card(self, parent, title, amount, row, col, color="#3a7ebf"):
        f = ctk.CTkFrame(parent, fg_color="#2b2b2b", corner_radius=10)
        f.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(f, text=title, font=("Arial", 16, "bold"), text_color="gray").pack(pady=(20, 5))
        ctk.CTkLabel(f, text=f"{amount:,.2f} EGP", font=("Arial", 28, "bold"), text_color=color).pack(pady=(0, 20))

    def calculate_financials(self):
        for w in self.card_frame.winfo_children(): w.destroy()

        gross_revenue = 0.0
        sales_returns_rma = 0.0
        cogs = 0.0
        
        delivery_losses = 0.0
        commission_losses = 0.0
        defective_shrinkage = 0.0
        
        retained_deposits = 0.0
        uncollected_cash = 0.0

        all_orders = db.collection("sales_orders").get()
        
        for o in all_orders:
            data = o.to_dict()
            status = data.get("status", "")
            if status in ["PENDING", "CANCELLED"]: continue

            total_val = float(data.get("total_sale_value", 0))
            deposit = float(data.get("deposit_paid", 0))
            payout = float(data.get("payout_received", 0))
            
            # Gross Revenue & COGS applies to all non-pending/cancelled
            gross_revenue += total_val
            
            # Calculate COGS (only for items that didn't come back good)
            for item in data.get("items", []):
                cogs += float(item.get("landed_cost", 0)) * int(item.get("qty", 0))

            if status in ["CONFIRMED", "SHIPPED", "DELIVERED"]:
                uncollected_cash += (total_val - deposit)
                
            elif status == "COMPLETED":
                # Expected remainder = Total - deposit. If payout < expected, it's a commission loss.
                expected_payout = total_val - deposit
                if payout < expected_payout:
                    commission_losses += (expected_payout - payout)
                    
            elif status == "RETURNED":
                # It was returned. Reverse Revenue and COGS.
                gross_revenue -= total_val
                for item in data.get("items", []):
                    cogs -= float(item.get("landed_cost", 0)) * int(item.get("qty", 0))
                
                # Add back Defective Loss to COGS equivalent
                defective_shrinkage += float(data.get("defective_loss", 0))
                
                if "rma_refund" in data:
                    # It was a completed order returned later
                    sales_returns_rma += float(data.get("rma_refund", 0))
                else:
                    # It was an active return (rejected by courier)
                    delivery_losses += float(data.get("return_fees", 0))
                    retained_deposits += deposit

        net_revenue = gross_revenue - sales_returns_rma
        gross_profit = net_revenue - cogs
        total_losses = delivery_losses + commission_losses + defective_shrinkage
        net_profit = gross_profit + retained_deposits - total_losses

        self.create_card(self.card_frame, "1. Gross Revenue", gross_revenue, 0, 0)
        self.create_card(self.card_frame, "2. Sales Returns (RMA)", sales_returns_rma, 0, 1, color="#a32e2e")
        self.create_card(self.card_frame, "3. Net Revenue", net_revenue, 0, 2)
        
        self.create_card(self.card_frame, "4. COGS (Cost of Goods)", cogs, 1, 0, color="#c27b1f")
        self.create_card(self.card_frame, "5. Gross Profit", gross_profit, 1, 1, color="#2e7d32")
        self.create_card(self.card_frame, "6. Retained Deposits (Income)", retained_deposits, 1, 2)
        
        self.create_card(self.card_frame, "7. Total Business Losses", total_losses, 2, 0, color="#a32e2e")
        self.create_card(self.card_frame, "8. Uncollected Cash (Pending Payout)", uncollected_cash, 2, 1, color="#8e24aa")
        self.create_card(self.card_frame, "9. NET PROFIT", net_profit, 2, 2, color="green")