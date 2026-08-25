import { z } from "zod";


const BaseSpecSchema = z.object({
  title: z.string().min(1),
  source: z.string().min(1),
});

export const TimeSeriesChartSpecSchema = BaseSpecSchema.extend({
  type: z.literal("timeSeries"),
  x: z.string().min(1),
  y: z.array(z.string().min(1)).min(1),
});

export const PolicyComparisonChartSpecSchema = BaseSpecSchema.extend({
  type: z.literal("policyComparison"),
  metric: z.string().min(1),
  groupBy: z.literal("policy"),
  scenario: z.string().min(1),
  confidenceInterval: z.boolean().default(false),
});

export const DistributionChartSpecSchema = BaseSpecSchema.extend({
  type: z.literal("distribution"),
  metric: z.string().min(1),
  groupBy: z.literal("policy"),
  scenario: z.string().min(1),
  confidenceInterval: z.boolean().default(false),
});

export const TradeoffChartSpecSchema = BaseSpecSchema.extend({
  type: z.literal("tradeoff"),
  x: z.string().min(1),
  y: z.string().min(1),
  groupBy: z.literal("policy"),
  scenario: z.string().min(1),
  reference: z.string().optional(),
});

export const FloorHeatmapChartSpecSchema = BaseSpecSchema.extend({
  type: z.literal("floorHeatmap"),
  metric: z.string().min(1),
});

export const MetricCardChartSpecSchema = BaseSpecSchema.extend({
  type: z.literal("metricCard"),
  metric: z.string().min(1),
  unit: z.string().optional(),
});

export const ConfidenceIntervalChartSpecSchema = BaseSpecSchema.extend({
  type: z.literal("confidenceInterval"),
  metric: z.string().min(1),
  scenario: z.string().min(1),
  groupBy: z.literal("policy"),
});

export const ExperimentMatrixChartSpecSchema = BaseSpecSchema.extend({
  type: z.literal("experimentMatrix"),
  metric: z.string().min(1),
  row: z.literal("scenario"),
  column: z.literal("policy"),
});

export const ChartSpecSchema = z.discriminatedUnion("type", [
  TimeSeriesChartSpecSchema,
  PolicyComparisonChartSpecSchema,
  DistributionChartSpecSchema,
  TradeoffChartSpecSchema,
  FloorHeatmapChartSpecSchema,
  MetricCardChartSpecSchema,
  ConfidenceIntervalChartSpecSchema,
  ExperimentMatrixChartSpecSchema,
]);

export type ChartSpec = z.infer<typeof ChartSpecSchema>;

export function parseChartSpec(input: unknown): ChartSpec {
  return ChartSpecSchema.parse(input);
}
