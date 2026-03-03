import React from 'react';
import { Button } from 'react-native';
import { login } from '../services/AuthService';

export const LoginButton = () => {
    return (
        <Button title="Log In" onPress={() => login('user', 'pass')} />
    );
};
