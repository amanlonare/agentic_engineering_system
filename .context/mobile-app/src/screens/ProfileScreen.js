import React from 'react';
import { View, Text } from 'react-native';

export const ProfileScreen = ({ user }) => {
    return (
        <View>
            <Text>User Profile: {user.name}</Text>
        </View>
    );
};
