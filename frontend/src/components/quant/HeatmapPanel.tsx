export default function HeatmapPanel() {

    const assets = [
  
      { name: "BTC", value: "+1.8%" },
      { name: "ETH", value: "+0.7%" },
      { name: "SPX", value: "-0.3%" },
      { name: "DXY", value: "+0.9%" },
      { name: "VIX", value: "+4.1%" },
      { name: "GOLD", value: "-0.2%" },
    ];
  
    return (
  
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5">
  
        <h2 className="text-xl font-bold text-orange-400 mb-5">
          Cross Asset Heatmap
        </h2>
  
        <div className="grid grid-cols-2 xl:grid-cols-3 gap-4">
  
          {assets.map((asset, index) => (
  
            <div
              key={index}
              className="bg-zinc-900 rounded-xl p-5 border border-zinc-800"
            >
  
              <p className="text-zinc-500 text-sm">
                {asset.name}
              </p>
  
              <p
                className={`
                  text-2xl font-bold mt-2
  
                  ${asset.value.includes("+")
                    ? "text-green-400"
                    : "text-red-400"}
                `}
              >
  
                {asset.value}
  
              </p>
  
            </div>
  
          ))}
  
        </div>
  
      </div>
    );
  }