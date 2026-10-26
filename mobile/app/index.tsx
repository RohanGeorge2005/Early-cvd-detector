import { ActivityIndicator, View } from "react-native";
import { Redirect } from "expo-router";
import { useAuth } from "@/lib/auth";
export default function Index(){const {ready,token}=useAuth();if(!ready)return <View style={{flex:1,alignItems:"center",justifyContent:"center"}}><ActivityIndicator size="large" color="#176b87"/></View>;return <Redirect href={token?"/(tabs)":"/login"}/>;}
