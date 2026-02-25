import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';

export const PromoBanner = ({ title, description, onAccept }) => {
    return (
        <View style={styles.container}>
            <Text style={styles.title}>{title}</Text>
            <Text style={styles.desc}>{description}</Text>
            <TouchableOpacity style={styles.button} onPress={onAccept}>
                <Text style={styles.buttonText}>Claim Now</Text>
            </TouchableOpacity>
        </View>
    );
};

const styles = StyleSheet.create({
    container: { padding: 16, backgroundColor: '#f0f0f0', borderRadius: 8 },
    title: { fontSize: 18, fontWeight: 'bold' },
    desc: { marginVertical: 8 },
    button: { backgroundColor: '#007bff', padding: 10, borderRadius: 5 },
    buttonText: { color: 'white', textAlign: 'center' }
});
