export default function RegimeTimeline({
  market,
}: any) {

  const regimes = [

    "TREND",
    "VOLATILE",
    "CRISIS",
    "RECOVERY",
    "CHOP",
  ];

  return (

    <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-5">

      <h2 className="text-xl font-bold text-cyan-400 mb-5">
        Regime Timeline
      </h2>

      <div className="flex overflow-hidden rounded-xl">

        {regimes.map((regime, index) => (

          <div
            key={index}
            className={`
              flex-1 p-4 text-center text-sm font-bold border-r border-black

              ${regime === "TREND" ? "bg-green-500/30 text-green-300" : ""}
              ${regime === "VOLATILE" ? "bg-yellow-500/30 text-yellow-300" : ""}
              ${regime === "CRISIS" ? "bg-red-500/30 text-red-300" : ""}
              ${regime === "RECOVERY" ? "bg-cyan-500/30 text-cyan-300" : ""}
              ${regime === "CHOP" ? "bg-zinc-700 text-zinc-300" : ""}
            `}
          >

            {regime}

          </div>

        ))}

      </div>

    </div>
  );
}