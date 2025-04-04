// Copyright (C) 2021 Bosutech XXI S.L.
//
// nucliadb is offered under the AGPL v3.0 and as commercial software.
// For commercial licensing, contact us at info@nuclia.com.
//
// AGPL:
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as
// published by the Free Software Foundation, either version 3 of the
// License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program. If not, see <http://www.gnu.org/licenses/>.
//
use std::path::PathBuf;
use std::sync::{Arc, RwLock};

use crate::prelude::*;
use crate::protos::*;
use crate::Channel;

pub type RelationsReaderPointer = Arc<dyn RelationReader>;
pub type RelationsWriterPointer = Arc<RwLock<dyn RelationWriter>>;

#[derive(Clone)]
pub struct RelationConfig {
    pub path: PathBuf,
    pub channel: Channel,
}

pub trait RelationReader:
    ReaderChild<Request = RelationSearchRequest, Response = RelationSearchResponse>
{
    fn get_edges(&self) -> NodeResult<EdgeList>;
    fn get_node_types(&self) -> NodeResult<TypeList>;
    fn count(&self) -> NodeResult<usize>;
}

pub trait RelationWriter: WriterChild {}
