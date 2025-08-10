export const storage = {
  async getMiningStats() {
    return { isActive: false };
  },
  async updateMiningStats(_stats: { isActive: boolean; threads: number }) {
    // placeholder
  },
  async getCurrentBalance() {
    return 0;
  },
  async updateBalance(_balance: number) {
    // placeholder
  }
};
