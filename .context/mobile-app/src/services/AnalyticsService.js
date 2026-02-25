export const AnalyticsService = {
    trackEvent: (eventName, properties) => {
        console.log(`[Analytics] ${eventName}`, properties);
        // Send to segment/mixpanel
    },
    trackEngagement: (userId, duration) => {
        console.log(`[Analytics] User ${userId} engaged for ${duration}s`);
    }
};
