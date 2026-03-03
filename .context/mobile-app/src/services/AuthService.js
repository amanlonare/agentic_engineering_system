export const login = async (username, password) => {
    console.log("Mock login API call");
    return { token: "mock_token" };
};

export const logout = async () => {
    console.log("Mock logout");
};
