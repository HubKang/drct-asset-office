import { Navigate, Route, Routes } from "react-router-dom";
import AdminLayout from "@/layouts/AdminLayout";
import { routeRegistry } from "@/router/routeRegistry";

function AppRouter() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        {routeRegistry.map((route) => (
          <Route key={route.routeKey} path={route.path} element={route.component} />
        ))}
      </Route>
    </Routes>
  );
}

export default AppRouter;
