"use client";

import Plot from "react-plotly.js";
import { useTranslate } from "@/lib/translation-helpers";
import { VISUALISATION_RESULT } from "./translations";

interface VisualisationResultProps {
    stageResult: any;
    title?: string;
}

export default function VisualisationResult({ stageResult, title }: VisualisationResultProps) {
    const translate = useTranslate();

    if (!stageResult || stageResult.status !== "success") {
        return <p className="text-muted-foreground">{translate(VISUALISATION_RESULT.no_visualisation_data)}</p>;
    }

    const chartData = stageResult.chart_data;

    if (chartData?.error) {
        return <p className="text-red-500">{chartData.error}</p>;
    }

    if (!chartData) {
        return <p className="text-muted-foreground">{translate(VISUALISATION_RESULT.no_visualisation_data)}</p>;
    }

    const config = {
        responsive: true,
        toImageButtonOptions: {
            format: 'png',
            filename: 'chart',
            scale: 2,
        },
    };

    // Bar chart
    if (chartData.type === "bar") {
        const trace = {
            type: "bar",
            x: chartData.x,
            y: chartData.y,
            marker: {
                color: "#3b82f6",
            },
            name: chartData.y_label || translate(VISUALISATION_RESULT.chart_value),
        };
        const layout = {
            title: title || `${chartData.x_label} vs ${chartData.y_label || translate(VISUALISATION_RESULT.chart_count)}`,
            xaxis: { title: chartData.x_label || translate(VISUALISATION_RESULT.chart_category) },
            yaxis: { title: chartData.y_label || translate(VISUALISATION_RESULT.chart_value) },
            showlegend: false,
            responsive: true,
        };
        return (
            <div className="w-full h-[400px]">
                <Plot data={[trace]} layout={layout} config={config} className="w-full h-full" />
            </div>
        );
    }

    // Pie chart
    if (chartData.type === "pie") {
        const trace = {
            type: "pie",
            labels: chartData.labels,
            values: chartData.values,
            marker: {
                colors: ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"],
            },
        };
        const layout = {
            title: title || translate(VISUALISATION_RESULT.visualisation_distribution),
            showlegend: true,
            legend: { orientation: "h" },
            responsive: true,
        };
        return (
            <div className="w-full h-[400px]">
                <Plot data={[trace]} layout={layout} config={config} className="w-full h-full" />
            </div>
        );
    }

    // Line chart
    if (chartData.type === "line") {
        let traces: any[] = [];
        if (chartData.series) {
            const colors = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6"];
            traces = chartData.series.map((s: any, index: number) => ({
                type: "scatter",
                mode: "lines+markers",
                x: chartData.x,
                y: s.y,
                name: s.name,
                line: { color: colors[index % colors.length] },
                marker: { symbol: "circle" },
            }));
        } else {
            traces = [{
                type: "scatter",
                mode: "lines+markers",
                x: chartData.x,
                y: chartData.y,
                name: chartData.y_label || translate(VISUALISATION_RESULT.chart_value),
                line: { color: "#3b82f6" },
                marker: { symbol: "circle" },
            }];
        }
        const layout = {
            title: title || chartData.x_label || translate(VISUALISATION_RESULT.visualisation_trend),
            xaxis: { title: chartData.x_label || translate(VISUALISATION_RESULT.chart_x_axis) },
            yaxis: { title: chartData.y_label || translate(VISUALISATION_RESULT.chart_y_axis) },
            showlegend: true,
            legend: { orientation: "h" },
            responsive: true,
        };
        return (
            <div className="w-full h-[400px]">
                <Plot data={traces} layout={layout} config={config} className="w-full h-full" />
            </div>
        );
    }

    // Scatter plot
    if (chartData.type === "scatter") {
        const trace = {
            type: "scatter",
            mode: "markers",
            x: chartData.x,
            y: chartData.y,
            marker: {
                color: "#3b82f6",
                size: 10,
            },
            name: translate(VISUALISATION_RESULT.visualisation_data_points),
        };
        const layout = {
            title: title || `${chartData.x_label} vs ${chartData.y_label}`,
            xaxis: { title: chartData.x_label || translate(VISUALISATION_RESULT.chart_x_axis) },
            yaxis: { title: chartData.y_label || translate(VISUALISATION_RESULT.chart_y_axis) },
            showlegend: false,
            responsive: true,
        };
        return (
            <div className="w-full h-[400px]">
                <Plot data={[trace]} layout={layout} config={config} className="w-full h-full" />
            </div>
        );
    }

    // Fallback: show raw data
    return (
        <div>
            <p className="text-sm text-muted-foreground mb-2">{translate(VISUALISATION_RESULT.visualisation_raw_data)}</p>
            <pre className="p-4 bg-muted/30 rounded-md overflow-x-auto text-xs">
                {JSON.stringify(chartData, null, 2)}
            </pre>
        </div>
    );
}
