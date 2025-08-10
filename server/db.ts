export const db = {
  select: () => ({
    from: (_table: unknown) => ({
      where: (_condition: unknown) => ({
        limit: async (_n: number) => [] as any[]
      })
    })
  })
};
