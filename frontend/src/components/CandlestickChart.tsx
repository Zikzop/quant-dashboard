"use client";

import {
  ResponsiveContainer,
  ComposedChart,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Bar,
  Line,
} from "recharts";

export default function CandlestickChart({
  data,
}: {
  data: any[];
}) {

  const candleData = data.map((d) => ({
    ...d,
    body:
      d.close > d.open
        ? d.close - d.open
        : d.open - d.close,

    bottom:
      d.close > d.open
        ? d.open
        : d.close,
  }));

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">

      <h2 className="text-2xl font-bold text-green-400 mb-6">
        Candlestick Structure
      </h2>

      <div className="h-[500px]">

        <ResponsiveContainer width="100%" height="100%">

          <ComposedChart data={candleData}>

            <CartesianGrid
              stroke="#27272a"
              strokeDasharray="3 3"
            />

            <XAxis
              dataKey="time"
              stroke="#a1a1aa"
            />

            <YAxis
              stroke="#a1a1aa"
              domain={['dataMin - 1000', 'dataMax + 1000']}
            />

            <Tooltip
              contentStyle={{
                backgroundColor: "#18181b",
                border: "1px solid #27272a",
                borderRadius: "12px",
                color: "#fff",
              }}
            />

            <Bar
              dataKey="close"
              fill="#22c55e"
              radius={[4, 4, 0, 0]}
            />

            <Line
              type="monotone"
              dataKey="ema20"
              stroke="#06b6d4"
              strokeWidth={2}
              dot={false}
            />

            <Line
              type="monotone"
              dataKey="ema50"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
            />

          </ComposedChart>

        </ResponsiveContainer>

      </div>

    </div>
  );
}