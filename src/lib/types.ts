export type Source = "erpnext_report" | "erpnext_api" | "raw_fallback" | "gl_entry" | "sales_invoice" | "sales_invoice_item";

export interface Range {
  start: string;
  end: string;
}

interface Base {
  source: Source;
  range: Range;
  cached?: boolean;
  fallback_reason?: string;
}

export interface SalesTotals {
  total_sales: number;
  gross_sales: number;
  returns_total: number;
  invoice_count: number;
  return_count: number;
  avg_invoice_value: number;
  outstanding: number;
  total_qty: number;
}

export interface SalesKpis extends Base {
  previous_range: Range;
  current: SalesTotals;
  previous: SalesTotals;
  delta_pct: Record<keyof SalesTotals, number | null>;
}

export interface Invoice {
  name: string;
  posting_date: string;
  posting_time: string | null;
  customer: string;
  customer_name: string;
  base_grand_total: number;
  base_net_total: number;
  total_taxes_and_charges: number;
  discount_amount: number;
  outstanding_amount: number;
  status: string;
  is_return: number;
  is_pos: number;
  cost_center: string | null;
  pos_profile: string | null;
  set_warehouse: string | null;
  total_qty: number;
  due_date: string | null;
  outlet: string;
}

export interface InvoicesResponse extends Base {
  count: number;
  invoices: Invoice[];
}

export interface TrendPoint {
  period: string;
  total: number;
  invoice_count: number;
}

export interface SalesTrend extends Base {
  granularity: "day" | "month";
  points: TrendPoint[];
}

export interface TopItem {
  item_code: string;
  item_name: string;
  item_group: string | null;
  qty: number;
  amount: number;
  share_pct: number;
}

export interface TopItems extends Base {
  items: TopItem[];
  other_amount: number;
  total_amount: number;
  distinct_items: number;
}

export interface Outlet {
  outlet: string;
  cost_center: string | null;
  pos_profile: string | null;
  total: number;
  invoice_count: number;
  avg_invoice_value: number;
  outstanding: number;
  share_pct: number;
}

export interface OutletSales extends Base {
  outlets: Outlet[];
  total: number;
}

export interface BreakdownRow {
  account: string;
  label: string;
  amount: number;
  parent: string;
}

export interface Pnl extends Base {
  report?: string;
  revenue: number;
  expenses: number;
  net_profit: number;
  margin_pct: number | null;
  income_breakdown: BreakdownRow[];
  expense_breakdown: BreakdownRow[];
}

export interface PnlPoint {
  period: string;
  income: number;
  expense: number;
  net: number;
}

export interface PnlTrend extends Base {
  granularity: "day" | "month";
  points: PnlPoint[];
}

export interface AgeingBucket {
  bucket: string;
  amount: number;
}

export interface ArCustomer {
  customer: string;
  customer_name: string;
  invoiced: number;
  paid: number | null;
  outstanding: number;
  ageing: Record<string, number>;
}

export interface Receivables extends Base {
  as_on: string;
  total_outstanding: number;
  customer_count: number;
  ageing: AgeingBucket[];
  top_customers: ArCustomer[];
}

export interface CashAccount {
  account: string;
  label: string;
  type: "Cash" | "Bank";
  balance: number;
  inflow: number;
  outflow: number;
  net_movement: number;
}

export interface CashPosition extends Base {
  as_on: string;
  total: number;
  cash_total: number;
  bank_total: number;
  net_movement: number;
  accounts: CashAccount[];
}

export interface Summary {
  range: Range;
  sales: SalesKpis;
  pnl: Pnl;
  receivables: Receivables;
  cash: CashPosition;
  outlets: OutletSales;
  cached?: boolean;
}

// ---------------------------------------------------------------- sales analytics

export interface ComparePoint {
  index: number;
  period: string | null;
  previous_period: string | null;
  current: number | null;
  previous: number | null;
}

export interface SalesCompare extends Base {
  previous_range: Range;
  granularity: "day" | "month";
  points: ComparePoint[];
  current_total: number;
  previous_total: number;
  delta_pct: number | null;
}

export interface ItemGroupRow {
  item_group: string;
  qty: number;
  amount: number;
  items: number;
  share_pct: number;
}

export interface ItemGroupSales extends Base {
  groups: ItemGroupRow[];
  total_amount: number;
}

export interface HourPoint {
  hour: number;
  label: string;
  total: number;
  invoice_count: number;
  avg_per_day: number;
}

export interface HourlySales extends Base {
  active_days: number;
  points: HourPoint[];
  peak_hour: number | null;
}

export interface WeekdayPoint {
  weekday: string;
  total: number;
  invoice_count: number;
  occurrences: number;
  avg_per_day: number;
}

export interface WeekdaySales extends Base {
  points: WeekdayPoint[];
  best_weekday: string | null;
}

export interface DistributionBucket {
  bucket: string;
  min: number;
  max: number | null;
  invoice_count: number;
  total: number;
}

export interface InvoiceDistribution extends Base {
  buckets: DistributionBucket[];
  stats: { count: number; median: number; mean: number; min: number; max: number; p90: number };
}

export interface CustomerRow {
  customer: string;
  customer_name: string;
  total: number;
  invoice_count: number;
  avg_invoice_value: number;
  outstanding: number;
  last_invoice: string;
  share_pct: number;
}

export interface TopCustomers extends Base {
  customers: CustomerRow[];
  distinct_customers: number;
  total: number;
}

export interface PaymentMode {
  mode: string;
  amount: number;
  count: number;
  share_pct: number;
}

export interface PaymentModes extends Base {
  modes: PaymentMode[];
  total: number;
}

export interface WaterfallStep {
  label: string;
  amount: number;
  kind: "total" | "delta";
}

export interface SalesComposition extends Base {
  steps: WaterfallStep[];
  gross: number;
  discount: number;
  taxes: number;
  returns: number;
  net_sales: number;
  invoice_count: number;
  return_count: number;
  discount_pct: number;
}

// ------------------------------------------------------------ accounting analytics

export interface ApSupplier {
  supplier: string;
  supplier_name: string;
  supplier_group: string | null;
  invoiced: number;
  paid: number | null;
  outstanding: number;
  ageing: Record<string, number>;
}

export interface Payables extends Base {
  as_on: string;
  total_outstanding: number;
  supplier_count: number;
  ageing: AgeingBucket[];
  top_suppliers: ApSupplier[];
}

export interface PurchasePoint {
  period: string;
  purchases: number;
  purchase_count: number;
  sales: number;
}

export interface PurchasesTrend extends Base {
  granularity: "day" | "month";
  points: PurchasePoint[];
  total_purchases: number;
  total_sales: number;
  purchase_count: number;
  purchase_to_sales_pct: number | null;
}

export interface CashFlowPoint {
  period: string;
  inflow: number;
  outflow: number;
  net: number;
  balance: number;
}

export interface CashFlow extends Base {
  granularity: "day" | "month";
  points: CashFlowPoint[];
  total_inflow: number;
  total_outflow: number;
  net: number;
  opening: number;
  closing: number;
}

export interface ExpenseTrendPoint {
  period: string;
  total: number;
  [group: string]: number | string;
}

export interface ExpenseTrend extends Base {
  granularity: "day" | "month";
  groups: string[];
  points: ExpenseTrendPoint[];
  totals: { group: string; amount: number }[];
}

export interface BalanceSheet extends Base {
  as_on: string;
  report?: string;
  assets: number;
  liabilities: number;
  equity: number;
  provisional_profit_loss: number;
  current_assets: number;
  current_liabilities: number;
  current_ratio: number | null;
  asset_accounts: BreakdownRow[];
  liability_accounts: BreakdownRow[];
  equity_accounts: BreakdownRow[];
}
