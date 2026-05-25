"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";



export default function PriceChart({
  data,
}: {
  data: any[];
}) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">

      <h2 className="text-2xl font-bold text-green-400 mb-6">
        Price Structure
      </h2>

      <div className="h-[400px]">
        <ResponsiveContainer width="100%" height="100%">

          <LineChart data={data}>

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

            <Line
              type="monotone"
              dataKey="close"
              stroke="#22c55e"
              strokeWidth={3}
              dot={false}
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

          </LineChart>

        </ResponsiveContainer>
      </div>

    </div>
  );
}