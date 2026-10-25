export interface User {
  id: string;
  nom: string;
  prenom: string;
  email: string;
  role: string;
  uri?: string;
}

export interface AuthResponse {
  success: boolean;
  token: string;
  user: User;
}

export interface RegisterPayload {
  nom: string;
  prenom: string;
  email: string;
  motDePasse: string;
  role: string;
  age?: string;
  cin?: string;
  telephone?: string;
  adresse?: string;
  groupeSanguin?: string;
  specialite?: string;
}

export interface Personne {
  id: string;
  uri: string;
  nom: string;
  prenom: string;
  types: string[];
  age: string;
  cin: string;
  telephone: string;
  adresse: string;
  numeroDossier: string;
  groupeSanguin: string;
  specialite: string;
  service: string;
}
