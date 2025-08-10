export default {
  async validateTransaction(tx: unknown): Promise<boolean> {
    console.log('Validating transaction', tx);
    return true;
  }
};
