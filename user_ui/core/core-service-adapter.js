/* Phoenix User UI V0.1 — Core service boundary.
 *
 * Replace the development implementation with the authenticated API client
 * when the host integration is enabled. No UI component should access data
 * storage directly.
 */

export const coreServiceAdapter = {
  async getUserContext() {
    throw new Error("Core user-context service is not connected");
  },

  async getAuthorizedModuleCatalog() {
    throw new Error("Core module-discovery service is not connected");
  },

  async search() {
    throw new Error("Core search service is not connected");
  },

  async getNotifications() {
    throw new Error("Core notification service is not connected");
  },

  async getCommunicationContext() {
    throw new Error("Core communication service is not connected");
  },

  async openAIWorkspace() {
    throw new Error("Core AI service is not connected");
  }
};
