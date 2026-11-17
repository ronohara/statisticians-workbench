// frontend/app/visualize/page.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { DataValue } from "@/components/ui/data-value";
import { toast } from "sonner";
import { Loader2, Wand2, Download, XCircle, Lock, UserPlus } from "lucide-react";
import Link from "next/link";
import Plot from "react-plotly.js";
import html2canvas from "html2canvas";

// Import translations for this module
import { VISUALIZE } from "./translations";
import { COMMON } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";

interface VisualizationType {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  renderer: string;
  inputSchema: any;
  parameterSchema: any;
  defaultParameters: any;
}

interface UserRole {
  isAdmin: boolean;
  isGroupAdmin: boolean;
  isExampleUser: boolean;
}

function VisualizeContent() {
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const router = useRouter();
  const [types, setTypes] = useState<VisualizationType[]>([]);
  const [selectedType, setSelectedType] = useState<VisualizationType | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataInput, setDataInput] = useState("");
  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [saving, setSaving] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const tableRef = useRef<HTMLDivElement>(null);

  // User role for Example User detection
  const [userRole, setUserRole] = useState<UserRole | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  const isExampleUser = userRole?.isExampleUser === true;

  // Fetch user role
  useEffect(() => {
    const fetchUserRole = async () => {
      try {
        const res = await apiFetch("/api/user/role");
        if (res.ok) {
          const data = await res.json();
          setUserRole(data);
        }
      } catch (error) {
        console.error("Failed to fetch user role:", error);
      } finally {
        setLoadingRole(false);
      }
    };
    fetchUserRole();
  }, []);

  useEffect(() => {
    const fetchTypes = async () => {
      try {
        setLoading(true);
        setErrorMessage(null);
        const res = await apiFetch("/api/visualization-types");
        if (!res.ok) {
          let errorData: any = {};
          try {
            const text = await res.text();
            if (text) {
              errorData = JSON.parse(text);
            }
          } catch {
            // Use empty object
          }
          const errorMsg = getErrorMessageFromData(translate, errorData, VISUALIZE.load_error);
          throw new Error(errorMsg);
        }
        const data = await res.json();
        setTypes(data.types);
        if (data.types.length > 0) {
          setSelectedType(data.types[0]);
        }
      } catch (error: any) {
        const msg = error.message || translate(VISUALIZE.load_error);
        setErrorMessage(msg);
        toast.error(msg);
      } finally {
        setLoading(false);
      }
    };
    fetchTypes();
  }, []);

  useEffect(() => {
    if (selectedType) {
      setParameters(selectedType.defaultParameters || {});
      setDataInput("");
      setPreviewData(null);
      setErrorMessage(null);
      setSuccessMessage(null);
    }
  }, [selectedType]);

  const generateSampleData = () => {
    if (!selectedType) {
      return;
    }
    const slug = selectedType.slug;
    let sample: any = null;

    if (slug === "text_table") {
      sample = {
        columns: ["Name", "Age", "Score"],
        rows: [
          ["Alice", 30, 85],
          ["Bob", 25, 92],
          ["Charlie", 35, 78],
          ["Diana", 28, 95],
        ],
      };
    } else if (slug === "bar_chart" || slug === "pie_chart") {
      sample = {
        labels: ["A", "B", "C", "D", "E"],
        values: [10, 20, 30, 40, 50],
      };
    } else if (slug === "line_chart") {
      sample = {
        labels: ["Jan", "Feb", "Mar", "Apr", "May"],
        datasets: [
          { label: translate(VISUALIZE.sample_sales), data: [10, 20, 30, 40, 50] },
          { label: translate(VISUALIZE.sample_expenses), data: [15, 25, 35, 45, 55] },
        ],
      };
    } else if (slug === "scatter_plot") {
      sample = {
        x: [1, 2, 3, 4, 5, 6, 7, 8],
        y: [12, 18, 14, 22, 26, 30, 35, 42],
      };
    } else if (slug === "area_chart") {
      sample = {
        labels: ["Jan", "Feb", "Mar", "Apr", "May"],
        datasets: [
          { label: translate(VISUALIZE.sample_sales), data: [10, 20, 30, 40, 50] },
          { label: translate(VISUALIZE.sample_expenses), data: [5, 15, 25, 35, 45] },
        ],
      };
    } else if (slug === "horizontal_bar") {
      sample = {
        labels: ["Category A", "Category B", "Category C", "Category D", "Category E"],
        values: [42, 58, 35, 72, 28],
      };
    } else if (slug === "donut_chart") {
      sample = {
        labels: ["A", "B", "C", "D", "E"],
        values: [10, 20, 30, 40, 50],
      };
    } else if (slug === "histogram") {
      sample = {
        values: [12, 15, 18, 20, 22, 22, 25, 28, 30, 32, 35, 38, 40, 42, 45, 48, 50, 52, 55, 58, 60, 62, 65, 68, 70],
      };
    } else if (slug === "distribution") {
      sample = {
        values: [12, 15, 18, 20, 22, 22, 25, 28, 30, 32, 35, 38, 20, 22, 25, 28, 30, 32],
        groups: ["A", "A", "A", "A", "A", "A", "B", "B", "B", "B", "B", "B"],
      };
    } else {
      sample = {
        columns: [translate(VISUALIZE.sample_item), translate(VISUALIZE.sample_value)],
        rows: [
          ["Item 1", 100],
          ["Item 2", 200],
        ],
      };
    }

    const jsonStr = JSON.stringify(sample, null, 2);
    setDataInput(jsonStr);
    setPreviewData(sample);
    const msg = translate(VISUALIZE.sample_generated);
    setSuccessMessage(msg);
    toast.success(msg);
  };

  const handleDataChange = (value: string) => {
    setDataInput(value);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const parsed = JSON.parse(value);
      setPreviewData(parsed);
    } catch (e) {
      // Invalid JSON, don't update preview
    }
  };

  const downloadTableAsPNG = async () => {
    if (!tableRef.current) return;
    try {
      const canvas = await html2canvas(tableRef.current, {
        scale: 2,
        backgroundColor: "#ffffff",
        logging: false,
        useCORS: true,
        allowTaint: false,
      });
      const link = document.createElement("a");
      link.download = "table.png";
      link.href = canvas.toDataURL("image/png");
      link.click();
      const msg = translate(VISUALIZE.download_success);
      setSuccessMessage(msg);
      toast.success(msg);
    } catch (error: any) {
      const msg = error.message || translate(VISUALIZE.download_error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const renderVisualization = () => {
    if (!selectedType || !previewData) {
      return <p className="text-muted-foreground">{translate(VISUALIZE.no_data)}</p>;
    }

    const slug = selectedType.slug;
    const params = parameters;

    if (slug === "text_table") {
      return renderTextTable(previewData, params);
    }
    if (slug === "bar_chart") {
      return renderBarChart(previewData, params);
    }
    if (slug === "pie_chart") {
      return renderPieChart(previewData, params);
    }
    if (slug === "line_chart") {
      return renderLineChart(previewData, params);
    }
    if (slug === "scatter_plot") {
      return renderScatterPlot(previewData, params);
    }
    if (slug === "area_chart") {
      return renderAreaChart(previewData, params);
    }
    if (slug === "horizontal_bar") {
      return renderHorizontalBar(previewData, params);
    }
    if (slug === "donut_chart") {
      return renderDonutChart(previewData, params);
    }
    if (slug === "histogram") {
      return renderHistogram(previewData, params);
    }
    if (slug === "distribution") {
      return renderDistribution(previewData, params);
    }

    return <p className="text-muted-foreground">{translate(VISUALIZE.unsupported)}</p>;
  };

  const renderTextTable = (data: any, params: any) => {
    if (!data.columns || !data.rows) {
      return <p className="text-red-500">{translate(VISUALIZE.invalid_data)}</p>;
    }
    return (
      <div>
        <div className="flex justify-end mb-2">
          <Button variant="outline" size="sm" onClick={downloadTableAsPNG} disabled={isExampleUser}>
            <Download className="me-2 h-4 w-4" />
            {translate(VISUALIZE.download_png)}
          </Button>
        </div>
        <div ref={tableRef} className="overflow-x-auto bg-white p-4 rounded-md">
          <table className="w-full border-collapse border border-slate-300">
            <thead>
              <tr>
                {data.columns.map((col: string, i: number) => (
                  <th key={i} className="border border-slate-300 px-4 py-2 bg-slate-100 text-start">{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row: any[], i: number) => (
                <tr key={i} className={params.striped && i % 2 === 0 ? "bg-slate-50" : ""}>
                  {row.map((cell: any, j: number) => (
                    <td key={j} className="border border-slate-300 px-4 py-2"><DataValue value={String(cell)} /></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {params.title && <p className="mt-2 text-sm font-semibold text-center">{params.title}</p>}
        </div>
      </div>
    );
  };

  const renderBarChart = (data: any, params: any) => {
    if (!data.labels || !data.values) {
      return <p className="text-red-500">{translate(VISUALIZE.invalid_data)}</p>;
    }
    const trace = {
      type: "bar",
      x: data.labels,
      y: data.values,
      marker: {
        color: params.colors ? params.colors[0] : "#3b82f6",
      },
      name: params.title || "Bar Chart",
    };
    const layout = {
      title: params.title || "",
      showlegend: params.showLegend !== false,
      legend: { orientation: "h" },
    };
    const config = {
      responsive: true,
      toImageButtonOptions: {
        format: 'png',
        filename: 'chart',
        scale: 2,
      },
    };
    return <Plot data={[trace]} layout={layout} config={config} className="w-full h-[400px]" />;
  };

  const renderPieChart = (data: any, params: any) => {
    if (!data.labels || !data.values) {
      return <p className="text-red-500">{translate(VISUALIZE.invalid_data)}</p>;
    }
    const trace = {
      type: "pie",
      labels: data.labels,
      values: data.values,
      marker: {
        colors: ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"],
      },
      name: params.title || "Pie Chart",
    };
    const layout = {
      title: params.title || "",
      showlegend: params.showLegend !== false,
      legend: { orientation: "h" },
    };
    const config = {
      responsive: true,
      toImageButtonOptions: {
        format: 'png',
        filename: 'chart',
        scale: 2,
      },
    };
    return <Plot data={[trace]} layout={layout} config={config} className="w-full h-[400px]" />;
  };

  const renderLineChart = (data: any, params: any) => {
    if (!data.labels || !data.datasets) {
      return <p className="text-red-500">{translate(VISUALIZE.invalid_data)}</p>;
    }
    const traces = data.datasets.map((ds: any, index: number) => ({
      type: "scatter",
      mode: "lines+markers",
      x: data.labels,
      y: ds.data,
      name: ds.label || `Dataset ${index + 1}`,
      line: { color: ["#3b82f6", "#ef4444", "#10b981", "#f59e0b"][index % 4] },
      marker: { symbol: "circle" },
    }));
    const layout = {
      title: params.title || "",
      showlegend: params.showLegend !== false,
      legend: { orientation: "h" },
      xaxis: { title: "" },
      yaxis: { title: "" },
    };
    const config = {
      responsive: true,
      toImageButtonOptions: {
        format: 'png',
        filename: 'chart',
        scale: 2,
      },
    };
    return <Plot data={traces} layout={layout} config={config} className="w-full h-[400px]" />;
  };

  const renderScatterPlot = (data: any, params: any) => {
    if (!data.x || !data.y) {
      return <p className="text-red-500">{translate(VISUALIZE.invalid_data)}</p>;
    }
    const trace = {
      type: "scatter",
      mode: "markers",
      x: data.x,
      y: data.y,
      marker: {
        size: params.markerSize || 6,
        color: params.markerColor || "#3b82f6",
      },
      name: params.title || "Scatter Plot",
    };
    const layout = {
      title: params.title || "",
      showlegend: params.showLegend !== false,
      legend: { orientation: "h" },
      xaxis: { title: "" },
      yaxis: { title: "" },
    };
    const config = {
      responsive: true,
      toImageButtonOptions: { format: 'png', filename: 'chart', scale: 2 },
    };
    return <Plot data={[trace]} layout={layout} config={config} className="w-full h-[400px]" />;
  };

  const renderAreaChart = (data: any, params: any) => {
    if (!data.labels || !data.datasets) {
      return <p className="text-red-500">{translate(VISUALIZE.invalid_data)}</p>;
    }
    const traces = data.datasets.map((ds: any, index: number) => ({
      type: "scatter",
      mode: "lines",
      x: data.labels,
      y: ds.data,
      name: ds.label || `Dataset ${index + 1}`,
      fill: "tozeroy",
      fillcolor: `rgba(59,130,246,${params.fillOpacity || 0.3})`,
      line: { color: params.lineColor || "#3b82f6" },
    }));
    const layout = {
      title: params.title || "",
      showlegend: params.showLegend !== false,
      legend: { orientation: "h" },
      xaxis: { title: "" },
      yaxis: { title: "" },
    };
    const config = {
      responsive: true,
      toImageButtonOptions: { format: 'png', filename: 'chart', scale: 2 },
    };
    return <Plot data={traces} layout={layout} config={config} className="w-full h-[400px]" />;
  };

  const renderHorizontalBar = (data: any, params: any) => {
    if (!data.labels || !data.values) {
      return <p className="text-red-500">{translate(VISUALIZE.invalid_data)}</p>;
    }
    const trace = {
      type: "bar",
      orientation: "h",
      x: data.values,
      y: data.labels,
      marker: { color: params.barColor || "#3b82f6" },
      name: params.title || "Horizontal Bar",
    };
    const layout = {
      title: params.title || "",
      showlegend: params.showLegend !== false,
      legend: { orientation: "h" },
      xaxis: { title: "" },
      yaxis: { title: "", automargin: true },
    };
    const config = {
      responsive: true,
      toImageButtonOptions: { format: 'png', filename: 'chart', scale: 2 },
    };
    return <Plot data={[trace]} layout={layout} config={config} className="w-full h-[400px]" />;
  };

  const renderDonutChart = (data: any, params: any) => {
    if (!data.labels || !data.values) {
      return <p className="text-red-500">{translate(VISUALIZE.invalid_data)}</p>;
    }
    const trace = {
      type: "pie",
      labels: data.labels,
      values: data.values,
      hole: params.holeSize || 0.4,
      marker: { colors: ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"] },
      name: params.title || "Donut Chart",
    };
    const layout = {
      title: params.title || "",
      showlegend: params.showLegend !== false,
      legend: { orientation: "h" },
    };
    const config = {
      responsive: true,
      toImageButtonOptions: { format: 'png', filename: 'chart', scale: 2 },
    };
    return <Plot data={[trace]} layout={layout} config={config} className="w-full h-[400px]" />;
  };

  const renderHistogram = (data: any, params: any) => {
    if (!data.values) {
      return <p className="text-red-500">{translate(VISUALIZE.invalid_data)}</p>;
    }
    const trace = {
      type: "histogram",
      x: data.values,
      nbinsx: params.binCount || 20,
      marker: { color: params.barColor || "#3b82f6" },
      name: params.title || "Histogram",
    };
    const layout = {
      title: params.title || "",
      showlegend: params.showLegend !== false,
      legend: { orientation: "h" },
      xaxis: { title: "" },
      yaxis: { title: "Frequency" },
    };
    const config = {
      responsive: true,
      toImageButtonOptions: { format: 'png', filename: 'chart', scale: 2 },
    };
    return <Plot data={[trace]} layout={layout} config={config} className="w-full h-[400px]" />;
  };

  const renderDistribution = (data: any, params: any) => {
    if (!data.values) {
      return <p className="text-red-500">{translate(VISUALIZE.invalid_data)}</p>;
    }
    const plotType = params.plotType || "violin";
    const trace: any = {
      type: plotType,
      y: data.values,
      name: params.title || "Distribution",
    };
    if (data.groups) {
      trace.x = data.groups;
      trace.type = plotType === "box" ? "box" : "violin";
    }
    const layout = {
      title: params.title || "",
      showlegend: params.showLegend !== false,
      legend: { orientation: "h" },
      yaxis: { title: "" },
    };
    const config = {
      responsive: true,
      toImageButtonOptions: { format: 'png', filename: 'chart', scale: 2 },
    };
    return <Plot data={[trace]} layout={layout} config={config} className="w-full h-[400px]" />;
  };

  const handleParamChange = (key: string, value: any) => {
    setParameters(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    if (!selectedType || !previewData) {
      const msg = translate(VISUALIZE.save_no_data);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }
    setSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await apiFetch("/api/visualization-instances", {
        method: "POST",
        body: JSON.stringify({
          visualizationTypeId: selectedType.id,
          parameters: parameters,
          dataSnapshot: previewData,
          outputId: null,
        }),
      });
      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, VISUALIZE.save_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      const msg = translate(VISUALIZE.save_success);
      setSuccessMessage(msg);
      toast.success(msg);
    } catch (error: any) {
      const msg = error.message || translate(VISUALIZE.save_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  if (!isLanguageLoaded || loading || loadingRole) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // If Example User, show read-only view
  // Normal user / Example User view

  if (errorMessage) {
    return (
      <div className="max-w-lg mx-auto py-12">
        <Card>
          <CardHeader>
            <CardTitle>{translate(VISUALIZE.title)}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-red-600">{errorMessage}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (types.length === 0) {
    return (
      <div className="max-w-lg mx-auto py-12">
        <Card>
          <CardHeader>
            <CardTitle>{translate(VISUALIZE.title)}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              {translate(VISUALIZE.no_types)}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">{translate(VISUALIZE.title)}</h1>
      <p className="text-sm text-muted-foreground">
        {translate(VISUALIZE.description)}
      </p>

      {isExampleUser && (
        <div className="p-4 bg-orange-50 border border-orange-200 rounded-md text-orange-800 text-center">
          <Lock className="h-6 w-6 mx-auto mb-2 text-orange-600" />
          <p className="text-sm mb-3">
            {translate(COMPONENTS.readonly_wrapper)}
          </p>
          <Link href="/register">
            <Button size="sm">
              <UserPlus className="h-4 w-4 me-2" />
              {translate(COMPONENTS.example_user_banner.register_button)}
            </Button>
          </Link>
        </div>
      )}

      {errorMessage && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
          <span className="text-sm">{errorMessage}</span>
          <button
            onClick={dismissError}
            className="text-red-500 hover:text-red-700"
            aria-label={translate(COMMON.dismiss)}
          >
            <XCircle className="h-5 w-5" />
          </button>
        </div>
      )}

      {successMessage && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between">
          <span className="text-sm">{successMessage}</span>
          <button
            onClick={dismissSuccess}
            className="text-green-500 hover:text-green-700"
            aria-label={translate(COMMON.dismiss)}
          >
            <span className="text-xl">&times;</span>
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{translate(VISUALIZE.config)}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="type-select">{translate(VISUALIZE.type)}</Label>
                <select
                  id="type-select"
                  value={selectedType ? String(selectedType.id) : ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (!val) return;
                    const type = types.find(t => t.id === parseInt(val));
                    setSelectedType(type || null);
                  }}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  <option value="">{translate(VISUALIZE.select_type)}</option>
                  {types.map((type) => {
                    const nameKey = `visualization_type.${type.slug}.name`;
                    const displayName = translate({ key: nameKey, fallback: type.name });
                    return (
                      <option key={type.id} value={String(type.id)}>
                        {displayName}
                      </option>
                    );
                  })}
                </select>
              </div>

              {selectedType && (
                <>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <Label>{translate(VISUALIZE.data)}</Label>
                      <Button variant="outline" size="sm" onClick={generateSampleData}>
                        <Wand2 className="me-2 h-3 w-3" />
                        {translate(VISUALIZE.generate_sample)}
                      </Button>
                    </div>
                    <textarea dir="ltr"
                      value={dataInput}
                      onChange={(e) => handleDataChange(e.target.value)}
                      rows={8}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
                      placeholder={translate(VISUALIZE.data_placeholder)}
                    />
                  </div>

                  {selectedType.parameterSchema && selectedType.parameterSchema.properties && (
                    <div className="space-y-3 border-t pt-3">
                      <Label>{translate(VISUALIZE.parameters)}</Label>
                      {Object.entries(selectedType.parameterSchema.properties).map(([key, prop]: [string, any]) => {
                        const currentValue = parameters[key] !== undefined ? parameters[key] : prop.default;
                        return (
                          <div key={key} className="flex items-center justify-between">
                            <span className="text-sm capitalize">{key}</span>
                            {prop.type === "boolean" ? (
                              <Switch
                                checked={currentValue}
                                onCheckedChange={(val) => handleParamChange(key, val)}
                              />
                            ) : prop.type === "string" ? (
                              <Input dir="auto"
                                value={currentValue || ""}
                                onChange={(e) => handleParamChange(key, e.target.value)}
                                className="w-48 h-8 text-sm"
                              />
                            ) : prop.type === "array" && prop.items && prop.items.type === "string" ? (
                              <Input dir="auto"
                                value={Array.isArray(currentValue) ? currentValue.join(", ") : ""}
                                onChange={(e) => {
                                  const arr = e.target.value.split(",").map(s => s.trim()).filter(Boolean);
                                  handleParamChange(key, arr);
                                }}
                                className="w-48 h-8 text-sm"
                              />
                            ) : (
                              <span className="text-xs text-muted-foreground">{translate(VISUALIZE.unsupported_parameter)}</span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="flex-1">
            <CardHeader>
              <CardTitle>{translate(VISUALIZE.preview)}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="min-h-[400px] flex items-center justify-center">
                {renderVisualization()}
              </div>
            </CardContent>
          </Card>
          <div className="flex gap-4">
            <Button onClick={handleSave} disabled={isExampleUser || saving}>
              {saving ? translate(COMMON.saving) : translate(VISUALIZE.save_instance)}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function VisualizePage() {
  return (
    <ProtectedRoute>
      <VisualizeContent />
    </ProtectedRoute>
  );
}