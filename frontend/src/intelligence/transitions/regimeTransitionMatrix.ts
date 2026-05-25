export interface TransitionProbability {
    from: string
    to: string
    probability: number
}

export const regimeTransitions: TransitionProbability[] = [
    {
        from: "TREND",
        to: "VOLATILE",
        probability: 0.42
    },

    {
        from: "VOLATILE",
        to: "CRISIS",
        probability: 0.17
    },

    {
        from: "RECOVERY",
        to: "TREND",
        probability: 0.63
    }
]