"use client"

export default function
    MarketIntelligenceStrip({
        market,
    }: any) {

    const state = market?.market_state

    if (!state) {
        return null
    }

    return (

        <div
            className="
      w-full
      border-y
      border-zinc-900
      bg-black
      px-6
      py-3
      flex
      items-center
      gap-10
      text-xs
      uppercase
      tracking-[0.25em]
      overflow-x-auto
      "
        >

            <div className="text-cyan-400">
                Regime {state.market_regime}
            </div>

            <div className="text-orange-400">
                Strength {state.trend_strength}
            </div>

            <div className="text-green-400">
                Direction {state.direction}
            </div>

            <div className="text-yellow-300">
                ADX {state.adx?.toFixed(2)}
            </div>

            <div className="text-fuchsia-400">
                +DI {state.plus_di?.toFixed(2)}
            </div>

            <div className="text-pink-400">
                -DI {state.minus_di?.toFixed(2)}
            </div>

        </div>
    )
}