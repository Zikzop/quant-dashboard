import CrossAssetHeatmap from "./CrossAssetHeatmap";

export default function HeatmapPanel({
  market,
}: {
  market: { correlation?: Record<string, unknown> };
}) {
  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5">
      <h2 className="text-xl font-bold text-orange-400 mb-5">
        Cross Asset Heatmap
      </h2>

      <CrossAssetHeatmap correlation={market?.correlation} />
    </div>
  );
}
