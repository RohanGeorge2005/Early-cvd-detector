import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { AuthProvider } from "@/lib/auth";
export default function RootLayout() { return <AuthProvider><StatusBar style="dark"/><Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: "#f3f7f8" } }}><Stack.Screen name="index"/><Stack.Screen name="login"/><Stack.Screen name="activate"/><Stack.Screen name="(tabs)"/><Stack.Screen name="assessment/[assessmentId]" options={{ headerShown: true, title: "Assessment details", headerTintColor: "#176b87", headerStyle: { backgroundColor: "#fff" } }}/></Stack></AuthProvider>; }
